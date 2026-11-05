from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Literal

from radar.domain.model.entities import ActorKind, FilesOn, ProposalAction, ProposalStatus, Risk
from radar.domain.model.history.changeset import Changeset, EntityChange, changeset_json
from radar.domain.validation.verdict import Finding, InvalidChangeset

Verdict = Literal[ProposalAction.APPROVE, ProposalAction.REJECT, ProposalAction.RETRACT]
MOVES: dict[ProposalAction, tuple[ProposalStatus, ProposalStatus]] = {
    ProposalAction.APPROVE: (ProposalStatus.SUGGESTED, ProposalStatus.APPROVED),
    ProposalAction.REJECT: (ProposalStatus.SUGGESTED, ProposalStatus.REJECTED),
    ProposalAction.RETRACT: (ProposalStatus.APPROVED, ProposalStatus.RETRACTED),
}

class ProposalError(ValueError):
    ...

@dataclass(frozen=True, slots=True)
class AppliedChange:
    change: str
    entity: str
    version: int

@dataclass(frozen=True, slots=True)
class Edit:
    at: str
    actor: str
    note: str

def _note(note: str) -> str:
    if not note.strip():
        raise ProposalError("every edit and decision needs a note")
    return note.strip()

def content_hash(author: str, subject: str | None, message: str | None, source_url: str | None,
                 changeset: Changeset | None) -> str:
    body = {"author": author, "changes": changeset_json(changeset)["changes"] if changeset else None,
            "message": message, "source_url": source_url, "subject": subject}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()

@dataclass(frozen=True, slots=True)
class Proposal:
    id: str
    files_on: FilesOn
    status: ProposalStatus
    changeset: Changeset | None
    subject: str | None
    reason: str
    actor_kind: ActorKind
    author: str
    created_at: str
    content_hash: str
    message: str | None = None
    source_url: str | None = None
    reports: int = 1
    reviewer: str | None = None
    note: str | None = None
    decided_at: str | None = None
    edits: tuple[Edit, ...] = ()
    applied: tuple[AppliedChange, ...] = ()
    undone: tuple[AppliedChange, ...] = ()
    token: str | None = None
    bundle: str | None = None

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(sorted({r for c in self.changeset.changes for r in c.source_refs})) if self.changeset else ()

    def edited(self, changeset: Changeset, actor: str, note: str, at: str) -> Proposal:
        if self.status != ProposalStatus.SUGGESTED:
            raise ProposalError(f"{self.id} is {self.status.value}: only a suggested proposal is edited")
        return replace(self, changeset=changeset, edits=(*self.edits, Edit(at, actor, _note(note))))

    def decided(self, decision: Verdict, reviewer: str, note: str, at: str,
                changes: tuple[AppliedChange, ...] = ()) -> Proposal:
        need, then = MOVES[decision]
        if self.status != need:
            raise ProposalError(f"{self.id} is {self.status.value}: only a {need.value} proposal can be {then.value}")
        if decision == ProposalAction.APPROVE and self.changeset is None:
            raise ProposalError(f"{self.id} holds no change yet: edit one in before approving it")
        return replace(self, status=then, reviewer=reviewer, note=_note(note), decided_at=at,
                       applied=changes if decision == ProposalAction.APPROVE else self.applied,
                       undone=changes if decision == ProposalAction.RETRACT else self.undone)

@dataclass(frozen=True, slots=True)
class Shown:
    proposal: Proposal
    changes: tuple[EntityChange, ...]
    problem: str | None = None

@dataclass(frozen=True, slots=True)
class Filed:
    proposal: Proposal
    refusals: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class AlreadyProposed:
    refusals: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class Unfiled:
    refusals: tuple[str, ...]

Receipt = Filed | AlreadyProposed | Unfiled

@dataclass(frozen=True, slots=True)
class Member:
    proposal: Proposal
    risk: Risk | None
    after: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class Refusal:
    proposal: Proposal
    findings: tuple[Finding, ...]

@dataclass(frozen=True, slots=True)
class Held:
    proposal: Proposal
    waits_on: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class Outcome:
    done: tuple[Proposal, ...]
    refused: tuple[Refusal, ...] = ()
    held: tuple[Held, ...] = ()

    def one(self) -> Proposal:
        if self.refused:
            raise InvalidChangeset(self.refused[0].findings)
        return self.done[0]

    @property
    def changed(self) -> bool:
        return any(p.status in (ProposalStatus.APPROVED, ProposalStatus.RETRACTED) for p in self.done)
