from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Sequence

from radar.domain.model.entities import Instant

class CrawlStatus(str, Enum):
    DUE = "due"
    READ = "read"
    UNREAD = "unread"

class PageKind(str, Enum):
    PRODUCT = "product"
    OTHER = "page"

@dataclass(frozen=True, slots=True)
class CrawlRecord:
    address: str
    site: str
    org: str
    kind: PageKind
    status: CrawlStatus
    next_due: Instant
    content_hash: str | None = None
    fetched_at: Instant | None = None
    reason: str | None = None

class CrawlRecords(Protocol):
    def listed(self, org: str) -> tuple[CrawlRecord, ...]:
        ...

    def save(self, records: Sequence[CrawlRecord]) -> None:
        ...

    def due(self, now: Instant) -> tuple[str, ...]:
        ...
