from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

class FeedReads(Protocol):
    def kind_of(self, entity_id: str) -> str:
        ...

    def records(self, ids: Sequence[str]) -> Mapping[str, Mapping[str, Any]]:
        ...

    def name_of(self, subject: str) -> str:
        ...

    def counts(self) -> Mapping[str, int]:
        ...

    def examples(self) -> Sequence[str]:
        ...

    def cursor(self) -> str | None:
        ...

    def advance(self, cursor: str) -> None:
        ...
