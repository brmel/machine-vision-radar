from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol

from radar.domain.model.entities import ProductCard
from radar.domain.ports.ai.usage_log import Ended, Outcome
from radar.domain.ports.web.reader import Page

Terms = Mapping[str, Mapping[str, tuple[str, ...]]]

@dataclass(frozen=True, slots=True)
class Reading:
    page: Page
    maker: str
    known: tuple[ProductCard, ...]
    terms: Terms

@dataclass(frozen=True, slots=True)
class RecordsDraft:
    files_on: Literal["create", "update"]
    reason: str
    subject: str | None
    records: tuple[Mapping[str, Any], ...]

@dataclass(frozen=True, slots=True)
class FileDraft:
    files_on: Literal["create", "update"]
    reason: str
    subject: str | None
    url: str

ProposalDraft = RecordsDraft | FileDraft

@dataclass(frozen=True, slots=True)
class Findings:
    proposals: tuple[ProposalDraft, ...]
    follow: tuple[str, ...]
    tokens_in: int
    tokens_out: int

    def ended(self) -> Ended:
        return Ended(Outcome.ANSWERED, self.tokens_in, self.tokens_out)

class ResearchAgent(Protocol):
    def research(self, reading: Reading) -> Findings:
        ...
