from __future__ import annotations

from typing import Protocol

from radar.domain.model.entities import AdminRecord, RecordRows, StoredFile

LISTED = ("Product", "Organization", "Document")

class Records(Protocol):
    def rows(self, kind: str, query: str = "", cursor: str | None = None,
             category: str | None = None) -> RecordRows:
        ...

    def record(self, entity: str) -> AdminRecord | None:
        ...

    def upload(self, content: bytes, mime: str) -> StoredFile:
        ...
