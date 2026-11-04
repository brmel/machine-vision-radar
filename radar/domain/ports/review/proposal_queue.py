from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from radar.domain.model.entities import ActorKind, FilesOn, LogEntryView, LogPage, ProposalStatus
from radar.domain.review.proposal import Proposal

@dataclass(frozen=True, slots=True)
class Query:
    status: ProposalStatus | None = None
    files_on: FilesOn | None = None
    actor_kind: ActorKind | None = None
    author: str | None = None
    bundle: str | None = None

@dataclass(frozen=True, slots=True)
class QueuePage:
    proposals: tuple[Proposal, ...]
    cursor: str | None
    total: int

class ProposalQueue(Protocol):
    def submit(self, proposal: Proposal, entry: LogEntryView) -> Proposal:
        ...

    def get(self, proposal_id: str) -> Proposal | None:
        ...

    def list(self, query: Query, cursor: str | None = None) -> QueuePage:
        ...

    def record(self, proposal: Proposal, entry: LogEntryView) -> Proposal:
        ...

    def log(self, actor: str | None = None, cursor: str | None = None) -> LogPage:
        ...
