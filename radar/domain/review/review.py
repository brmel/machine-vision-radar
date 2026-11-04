from __future__ import annotations

from dataclasses import replace
from typing import Callable, Sequence, assert_never

from radar.domain.model.changeset import Change, Changeset, EntityChange, PutEntity, Retract
from radar.domain.model.entities import ActorKind, FilesOn, LogEntryView, LogPage, ProposalAction, ProposalStatus
from radar.domain.model.history.ids import keyed
from radar.domain.model.history.projection import every_page
from radar.domain.model.schema import ModelSchema
from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.ports.catalog.catalog_writer import CatalogWriter
from radar.domain.ports.history.version_store import VersionStore
from radar.domain.ports.review.proposal_queue import ProposalQueue, Query, QueuePage
from radar.domain.read_model.derived.identity import ProductIdentity
from radar.domain.review.agents.drafts import references, without
from radar.domain.review.agents.duplicates import Proposed, merged, unproposed
from radar.domain.review.agents.tokens import Refused
from radar.domain.review.bundle import RANK, after, ordered, risk
from radar.domain.review.proposal import (AlreadyProposed, AppliedChange, Filed, Held, Member, Outcome, Proposal,
                                          ProposalError, Receipt, Refusal, Shown, Unfiled, Verdict, content_hash,
                                          findings)
from radar.domain.review.requests import (Agent, Approval, Bundle, Bundled, Changes, Decision, Draft, Enactment,
                                          Founder, Job, Picked, Reader, Rejection, Report, Retraction, Revision,
                                          Rollback, Submitter, Target, Withdrawal)
from radar.domain.review.views import OWNED
from radar.domain.validation.context import Finding, InvalidChangeset

FILES = {Founder: (Changes, Withdrawal, Rollback), Agent: (Changes,), Job: (Changes, Withdrawal), Reader: (Report,)}

def _by(changeset: Changeset, name: str, kind: ActorKind) -> Changeset:
    return Changeset(tuple(replace(c, actor=name, actor_kind=kind) for c in changeset.changes))

class Review:
    def __init__(self, queue: ProposalQueue, writer: CatalogWriter, versions: VersionStore, held: Callable[[], Catalog],
                 identity: ProductIdentity, schema: ModelSchema, clock: Callable[[], str]) -> None:
        self._queue, self._writer, self._versions, self._held, self._identity, self._schema, self._clock = (
            queue, writer, versions, held, identity, schema, clock)
        self._uncited = {t.name for t in schema.entities if t.provenance or t.name in OWNED}
        self._provenance = {t.name for t in schema.entities if t.provenance}
        self._on_approval = {t.name: tuple(f.name for f in t.fields if f.set_on_approval) for t in schema.entities}
        self._refs = references(schema)

    def submit(self, draft: Draft, by: Submitter) -> Shown:
        if not isinstance(draft, FILES[type(by)]):
            raise Refused(f"{by.name} files no {type(draft).__name__.lower()}")
        match draft:
            case Changes():
                return self._changes(draft, by, None)
            case Withdrawal(entity, reason, files_on):
                return self._file(files_on, reason, entity,
                                  self._writer.withdrawal(entity, reason.strip(), by.kind, by.name), by)
            case Rollback(entity, to, reason):
                rolled = Changeset((self._rolled_back(draft, by),))
                return self._file(FilesOn.ROLLBACK, f"Roll {entity} back to version {to}: {reason.strip()}", entity,
                                  rolled, by)
            case Report(subject, message, source_url):
                return self._file(FilesOn.REPORT, message, subject, None, by, message, source_url)
            case _:
                assert_never(draft)

    def file(self, bundle: Bundle, by: Agent | Job) -> tuple[Receipt, ...]:
        return tuple(self._filing(draft, bundle.id, by, ()) for draft in bundle.drafts)

    def decide(self, decision: Decision, by: Founder) -> Outcome:
        match decision:
            case Approval(target, note):
                return self._approved(*self._targets(target, ProposalStatus.SUGGESTED), note, by)
            case Rejection(target, note):
                acting, _ = self._targets(target, ProposalStatus.SUGGESTED)
                return Outcome(tuple(self._decided(p, ProposalAction.REJECT, note, by) for p in acting))
            case Retraction(target, note):
                return self._retracted(self._targets(target, ProposalStatus.APPROVED)[0], note, by)
            case Revision(proposal, changeset, note):
                self._sourced(changeset)
                stamped = _by(changeset, by.name, by.kind)
                self._writer.check(stamped)
                edited = self._get(proposal).edited(stamped, by.name, note, self._clock())
                return Outcome((self._queue.record(edited, self._entry(ProposalAction.EDIT, edited, by, note)),))
            case Enactment(draft):
                return Outcome((self._approve(self.submit(draft, by).proposal, draft.reason, by),))
            case _:
                assert_never(decision)

    def queue(self, query: Query, by: Founder | Agent | Job, cursor: str | None = None) -> QueuePage:
        return self._queue.list(replace(query, actor_kind=ActorKind.AGENT, author=by.name) if isinstance(by, Agent)
                                else query, cursor)

    def bundle(self, bundle: str, by: Founder) -> tuple[Member, ...]:
        proposals = self._bundled(bundle)
        risks = {p.id: risk([c for c in self._writer.preview(p.changeset)
                             if self._schema.kind_of(c.entity) not in self._provenance])
                 for p in proposals if p.status == ProposalStatus.SUGGESTED and p.changeset}
        waits = after(proposals, self._refs)
        first = lambda p: (RANK[risks[p.id]] if p.id in risks else len(RANK), p.created_at, p.id)
        return tuple(Member(p, risks.get(p.id), waits[p.id]) for p in ordered(proposals, waits, first))

    def proposal(self, proposal: str, by: Founder | Agent) -> Shown:
        found = self._get(proposal)
        if isinstance(by, Agent) and (found.actor_kind != ActorKind.AGENT or found.author != by.name):
            raise Refused(f"{proposal} is not a proposal of {by.name}'s")
        try:
            return Shown(found, self._changes_of(found))
        except ValueError as exc:
            return Shown(found, (), f"its change no longer applies: {exc}")

    def log(self, by: Founder, actor: str | None = None, cursor: str | None = None) -> LogPage:
        return self._queue.log(actor, cursor)

    def _get(self, proposal_id: str) -> Proposal:
        found = self._queue.get(proposal_id)
        if found is None:
            raise LookupError(f"no proposal {proposal_id}")
        return found

    def _bundled(self, bundle: str) -> list[Proposal]:
        proposals = [p for page in every_page(lambda cursor: self._queue.list(Query(bundle=bundle), cursor))
                     for p in page.proposals]
        if not proposals:
            raise LookupError(f"no bundle {bundle}")
        return proposals

    def _targets(self, target: Target, status: ProposalStatus) -> tuple[list[Proposal], list[Proposal]]:
        match target:
            case Picked(ids):
                picked = [self._get(i) for i in dict.fromkeys(ids)]
                return picked, picked
            case Bundled(bundle):
                members = self._bundled(bundle)
                return [p for p in members if p.status == status], members
            case _:
                assert_never(target)

    def _entry(self, action: ProposalAction, proposal: Proposal, by: Submitter, note: str | None,
               changes: tuple[AppliedChange, ...] = ()) -> LogEntryView:
        return LogEntryView(at=self._clock(), action=action, proposal=proposal.id, actor=by.name, actor_kind=by.kind,
                            note=note, changes=tuple(a.change for a in changes), correlation_id=by.correlation_id)

    def _sourced(self, changeset: Changeset) -> None:
        uncited = [n for n, c in enumerate(changeset.changes) if not c.source_refs
                   and self._schema.kind_of(c.entity) not in self._uncited]
        if uncited:
            raise ProposalError(f"changeset: changes[{uncited[0]}]: source_refs names at least one source the change "
                                "rests on")

    def _changes(self, draft: Changes, by: Submitter, bundle: str | None) -> Shown:
        if isinstance(by, Agent):
            mine = (p for page in every_page(lambda cursor: self.queue(Query(ProposalStatus.SUGGESTED), by, cursor))
                    for p in page.proposals)
            kind_of = lambda i: self._schema.kind_of(i) or ""
            draft = unproposed(merged(draft, self._held(), kind_of, self._identity), mine, kind_of, self._refs)
        self._sourced(draft.changeset)
        return self._file(draft.files_on, draft.reason, draft.subject, draft.changeset, by, source_url=draft.source_url,
                          bundle=bundle)

    def _file(self, files_on: FilesOn, reason: str, subject: str | None, changeset: Changeset | None, by: Submitter,
              message: str | None = None, source_url: str | None = None, bundle: str | None = None) -> Shown:
        if not reason.strip():
            raise ProposalError("a proposal needs a reason")
        stamped = _by(changeset, by.name, by.kind) if changeset else None
        changes = self._writer.check(stamped) if stamped else ()
        digest = content_hash(by.name, subject, message, source_url, stamped)
        proposal = Proposal(keyed("prp", digest), files_on, ProposalStatus.SUGGESTED, stamped, subject, reason.strip(),
                            by.kind, by.name, self._clock(), digest, message, source_url,
                            token=by.token.id if isinstance(by, Agent) else None, bundle=bundle)
        return Shown(self._queue.submit(proposal, self._entry(ProposalAction.SUBMIT, proposal, by, None)), changes)

    def _filing(self, draft: Changes, bundle: str, by: Agent | Job, refusals: tuple[str, ...]) -> Receipt:
        try:
            return Filed(self._changes(draft, by, bundle).proposal, refusals)
        except Proposed:
            return AlreadyProposed(refusals)
        except InvalidChangeset as exc:
            whole = draft.changeset.changes
            kept = without(whole, {f.entity_id for f in exc.findings if isinstance(f, Finding)}, self._refs)
            if 1 < len(kept) < len(whole) and kept[0] == whole[0]:
                return self._filing(replace(draft, changeset=Changeset(kept)), bundle, by, (*refusals, str(exc)))
            return Unfiled((*refusals, str(exc)))
        except ValueError as exc:
            return Unfiled((*refusals, str(exc)))

    def _rolled_back(self, draft: Rollback, by: Submitter) -> Change:
        if not draft.reason.strip():
            raise ProposalError("a rollback needs a reason")
        state = self._versions.get(draft.entity, draft.to)
        if state is None:
            raise LookupError(f"{draft.entity} has no version {draft.to}")
        return Change(PutEntity(state) if state else Retract(draft.entity),
                      f"Rollback to version {draft.to}: {draft.reason.strip()}", by.kind, by.name,
                      self._cited(draft.entity, draft.to))

    def _cited(self, entity: str, version: int) -> tuple[str, ...]:
        pages = every_page(lambda cursor: self._versions.history(entity, cursor))
        return tuple(next((v.source_refs for page in pages for v in page.versions if v.version == version), ()))

    def _decided(self, proposal: Proposal, verdict: Verdict, note: str, by: Founder,
                 made: tuple[AppliedChange, ...] = ()) -> Proposal:
        decided = proposal.decided(verdict, by.name, note, self._clock(), made)
        return self._queue.record(decided, self._entry(verdict, decided, by, decided.note, made))

    def _allowed(self, proposals: Sequence[Proposal], verdict: Verdict, note: str, by: Founder) -> None:
        for p in proposals:
            p.decided(verdict, by.name, note, self._clock())

    def _approved(self, proposals: Sequence[Proposal], fellows: Sequence[Proposal], note: str, by: Founder) -> Outcome:
        self._allowed(proposals, ProposalAction.APPROVE, note, by)
        waits = after(fellows, self._refs)
        done: list[Proposal] = []
        refused: list[Refusal] = []
        held: list[Held] = []
        for p in ordered(proposals, after(proposals, self._refs), lambda q: (q.created_at, q.id)):
            try:
                done.append(self._approve(p, note, by))
            except InvalidChangeset as exc:
                approved = {f.id for f in fellows if f.status == ProposalStatus.APPROVED} | {d.id for d in done}
                if missing := tuple(w for w in waits[p.id] if w not in approved):
                    held.append(Held(p, missing))
                else:
                    refused.append(Refusal(p, findings(exc)))
        return Outcome(tuple(done), tuple(refused), tuple(held))

    def _approve(self, proposal: Proposal, note: str, by: Founder) -> Proposal:
        changes = proposal.changeset.changes if proposal.changeset else ()
        stamped = Changeset(tuple(replace(self._dated(c), proposal=proposal.id) for c in changes))
        made = tuple(AppliedChange(e["id"], e["entity"], e["version"])
                     for e in self._writer.apply(stamped, by.correlation_id).events)
        return self._decided(proposal, ProposalAction.APPROVE, note, by, made)

    def _dated(self, change: Change) -> Change:
        if not isinstance(change.action, PutEntity):
            return change
        record = change.action.record
        lacking = [f for f in self._on_approval.get(self._schema.kind_of(record["id"]) or "", ())
                   if record.get(f) is None]
        return (replace(change, action=PutEntity({**record, **{f: self._clock() for f in lacking}})) if lacking
                else change)

    def _retracted(self, proposals: Sequence[Proposal], note: str, by: Founder) -> Outcome:
        self._allowed(proposals, ProposalAction.RETRACT, note, by)
        done: list[Proposal] = []
        refused: list[Refusal] = []
        for p in reversed(ordered(proposals, after(proposals, self._refs), lambda q: (q.created_at, q.id))):
            try:
                undo = Changeset(tuple(self._undo(p, a, note, by) for a in p.applied))
                made = tuple(AppliedChange(e["id"], e["entity"], e["version"])
                             for e in self._writer.apply(undo, by.correlation_id).events) if undo.changes else ()
                done.append(self._decided(p, ProposalAction.RETRACT, note, by, made))
            except InvalidChangeset as exc:
                refused.append(Refusal(p, findings(exc)))
            except ProposalError as exc:
                refused.append(Refusal(p, (str(exc),)))
        return Outcome(tuple(done), tuple(refused))

    def _undo(self, proposal: Proposal, applied: AppliedChange, note: str, by: Founder) -> Change:
        latest = self._versions.history(applied.entity).versions[0].version
        if latest != applied.version:
            raise ProposalError(f"{applied.entity} changed after {proposal.id} (it is at v{latest}): roll it back from "
                                "its history")
        before = self._versions.get(applied.entity, applied.version - 1) if applied.version > 1 else None
        cited = (next((c.source_refs for c in proposal.changeset.changes if c.entity == applied.entity), ())
                 if proposal.changeset else ())
        return Change(PutEntity(before) if before else Retract(applied.entity),
                      f"Retraction of {proposal.id}: {note.strip()}", by.kind, by.name, cited, proposal.id)

    def _changes_of(self, proposal: Proposal) -> tuple[EntityChange, ...]:
        if proposal.status == ProposalStatus.SUGGESTED:
            return self._writer.check(proposal.changeset) if proposal.changeset else ()
        return tuple(EntityChange(a.entity, self._versions.get(a.entity, a.version - 1) or None,
                                  self._versions.get(a.entity, a.version) or None)
                     for a in proposal.applied)
