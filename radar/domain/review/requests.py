from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal, Mapping, get_args

from radar.domain.model.history.changeset import Changeset, parse_changeset
from radar.domain.model.entities import ActorKind, FilesOn, ProposalAction
from radar.domain.review.agents.tokens import AgentToken

@dataclass(frozen=True, slots=True)
class Founder:
    name: str
    correlation_id: str
    kind: ClassVar[ActorKind] = ActorKind.HUMAN

@dataclass(frozen=True, slots=True)
class Agent:
    token: AgentToken
    correlation_id: str
    kind: ClassVar[ActorKind] = ActorKind.AGENT

    @property
    def name(self) -> str:
        return self.token.name

@dataclass(frozen=True, slots=True)
class Job:
    name: str
    correlation_id: str
    kind: ClassVar[ActorKind] = ActorKind.AGENT

@dataclass(frozen=True, slots=True)
class Reader:
    correlation_id: str
    name: ClassVar[str] = "public"
    kind: ClassVar[ActorKind] = ActorKind.HUMAN

Submitter = Founder | Agent | Job | Reader

ChangesOn = Literal[FilesOn.CREATE, FilesOn.UPDATE, FilesOn.MERGE, FilesOn.RETRACT, FilesOn.FEED]

@dataclass(frozen=True, slots=True)
class Changes:
    files_on: ChangesOn
    reason: str
    subject: str | None
    changeset: Changeset
    source_url: str | None = None

@dataclass(frozen=True, slots=True)
class Withdrawal:
    entity: str
    reason: str
    files_on: Literal[FilesOn.RETRACT, FilesOn.QUALITY] = FilesOn.RETRACT

@dataclass(frozen=True, slots=True)
class Rollback:
    entity: str
    to: int
    reason: str

@dataclass(frozen=True, slots=True)
class Report:
    subject: str
    message: str
    source_url: str | None = None

Draft = Changes | Withdrawal | Rollback | Report

@dataclass(frozen=True, slots=True)
class Bundle:
    id: str
    drafts: tuple[Changes, ...]

@dataclass(frozen=True, slots=True)
class Picked:
    ids: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class Bundled:
    id: str

Target = Picked | Bundled

@dataclass(frozen=True, slots=True)
class Approval:
    target: Target
    note: str

@dataclass(frozen=True, slots=True)
class Rejection:
    target: Target
    note: str

@dataclass(frozen=True, slots=True)
class Retraction:
    target: Target
    note: str

@dataclass(frozen=True, slots=True)
class Revision:
    proposal: str
    changeset: Changeset
    note: str

@dataclass(frozen=True, slots=True)
class Enactment:
    draft: Changes | Withdrawal

Decision = Approval | Rejection | Retraction | Revision | Enactment

def _text(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()

def _id(raw: Mapping[str, object], key: str) -> str | None:
    value = raw.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{key} is a record id")
    return value

def _whole(raw: Mapping[str, object], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} is a whole number")
    return value

def _object(raw: object, what: str) -> Mapping[str, object]:
    if not isinstance(raw, dict):
        raise ValueError(f"a {what} is a JSON object")
    return raw

def draft_of(raw: object) -> Draft:
    shape = _object(raw, "draft")
    files_on, reason, subject = shape.get("files_on"), _text(shape, "reason"), _id(shape, "subject")
    if files_on in get_args(ChangesOn) and shape.get("changeset") is not None:
        return Changes(FilesOn(files_on), reason, subject, parse_changeset(shape["changeset"]))
    if files_on in (FilesOn.RETRACT, FilesOn.QUALITY) and subject:
        return Withdrawal(subject, reason, FilesOn(files_on))
    if files_on == FilesOn.ROLLBACK and subject:
        return Rollback(subject, _whole(shape, "to"), reason)
    raise ValueError("files_on is create, update, merge, retract or feed with a changeset; retract or quality, or "
                     "rollback with `to`, "
                     "of the record `subject`")

def _target(shape: Mapping[str, object]) -> Target:
    ids, bundle = shape.get("proposals"), shape.get("bundle")
    if isinstance(bundle, str) and bundle and ids is None:
        return Bundled(bundle)
    if isinstance(ids, list) and ids and all(isinstance(i, str) for i in ids) and bundle is None:
        return Picked(tuple(ids))
    raise ValueError("a decision names its proposals (a list of ids) or its bundle (a run's id)")

def decision_of(raw: object) -> Decision:
    shape = _object(raw, "decision")
    note = _text(shape, "note")
    match shape.get("decision"):
        case ProposalAction.APPROVE:
            return Approval(_target(shape), note)
        case ProposalAction.REJECT:
            return Rejection(_target(shape), note)
        case ProposalAction.RETRACT:
            return Retraction(_target(shape), note)
        case ProposalAction.EDIT:
            return Revision(_text(shape, "proposal"), parse_changeset(shape.get("changeset")), note)
    raise ValueError("decision is approve, reject, retract or edit")
