from __future__ import annotations

from dataclasses import replace
from typing import Callable, Mapping

from radar.domain.model.history.changeset import Change, Changeset, PutEntity, as_record, put_of
from radar.domain.model.entities import FilesOn, Source
from radar.domain.model.history.ids import keyed
from radar.domain.model.model import Model
from radar.domain.ports.catalog.held_records import HeldRecords
from radar.domain.ports.ai.research_agent import ProposalDraft, RecordsDraft
from radar.domain.ports.review.proposing import Proposing
from radar.domain.ports.review.research_runs import ResearchRun, Step
from radar.domain.ports.web.reader import Page
from radar.domain.review.agents.drafts import PROVENANCE, references, without
from radar.domain.review.proposal import AlreadyProposed, Filed, Unfiled
from radar.domain.review.requests import Agent, Bundle, Changes
from radar.domain.validation.verdict import InvalidChangeset

RESEARCHER = "research"
Log = Callable[[ResearchRun, Step, str], ResearchRun]

class Filing:
    def __init__(self, review: Proposing, model: Model, held: HeldRecords, log: Log) -> None:
        self._review, self._model, self._held, self._log = review, model, held, log
        self._citing = frozenset(e.name for e in model.schema.entities
                                 if any(f.name == "source_refs" for f in e.fields))
        self._refs = references(model.schema)

    def read(self, page: Page, source_type: str) -> Change:
        address = page.link.address
        held = self._held.matching(Source, "url", address)
        source = (replace(held[0], retrieved_at=page.retrieved_at) if held
                  else Source(id=keyed("src", address), version=1, type=source_type, url=address,
                              title=page.title or None, retrieved_at=page.retrieved_at))
        return Change(PutEntity(source), f"Read on {address}", "agent", RESEARCHER, (source.id,))

    def cited(self, draft: RecordsDraft, source: str) -> tuple[tuple[Change, ...], str | None]:
        cited = ({**r, "source_refs": [source]} if self._model.schema.kind_of(r["id"]) in self._citing else r
                 for r in draft.records)
        changes, unparsed = [], []
        for record in filter(None, map(self._over_held, cited)):
            try:
                changes.append(Change(put_of(record, self._model), draft.reason, "agent", RESEARCHER, (source,)))
            except InvalidChangeset as exc:
                unparsed += exc.findings
        refused = {f.entity_id for f in unparsed}
        return without(tuple(changes), refused, self._refs), str(InvalidChangeset(unparsed)) if unparsed else None

    def _over_held(self, record: Mapping[str, object]) -> dict[str, object] | None:
        found = self._held.held(str(record["id"]))
        held = as_record(found) if found else {}
        over = {**held, **record}
        return None if held and all(over[k] == held.get(k) for k in over.keys() - set(PROVENANCE)) else over

    def filed(self, run: ResearchRun, step: Step, draft: ProposalDraft, reason: str, changes: tuple[Change, ...],
              by: Agent, source_url: str | None = None) -> ResearchRun:
        [filing] = self._review.file(Bundle(run.id,
                                            (Changes(FilesOn(draft.files_on), reason, draft.subject, Changeset(changes),
                                                     source_url),)), by)
        for refusal in filing.refusals:
            run = self._log(run, Step.REJECTED, f"{reason}: {refusal}")
        match filing:
            case Filed(proposal):
                return self._log(run, step, proposal.id)
            case AlreadyProposed():
                return self._log(run, Step.SKIPPED, f"{reason}: an open proposal holds it")
            case Unfiled():
                return run
