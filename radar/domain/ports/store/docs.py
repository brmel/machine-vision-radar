from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, Iterator, Mapping, Protocol, Sequence

Fields = dict[str, Any]

@dataclass(frozen=True, slots=True)
class Put:
    path: str
    fields: Fields
    create: bool = False

@dataclass(frozen=True, slots=True)
class Delete:
    path: str

@dataclass(frozen=True, slots=True)
class Increment:
    path: str
    by: dict[str, int | float]

Write = Put | Delete | Increment
BATCH = 500

class Docs(Protocol):
    def get(self, path: str) -> Fields | None:
        ...

    def get_many(self, paths: Sequence[str]) -> dict[str, Fields]:
        ...

    def list(self, collection: str) -> Iterator[tuple[str, Fields]]:
        ...

    def where(self, collection: str, field: str, values: Collection[Any],
              contains: bool = False) -> list[tuple[str, Fields]]:
        ...

    def after(self, collection: str, field: str, start: tuple[Any, str] | None) -> Iterator[tuple[str, Fields]]:
        ...

    def count(self, collection: str, where: Mapping[str, Any] | None = None) -> int:
        ...

    def page(self, collection: str, cursor: str | None = None, limit: int = 20,
             where: Mapping[str, Any] | None = None) -> list[tuple[str, Fields]]:
        ...

    def group(self, collection_id: str) -> Iterator[tuple[str, Fields]]:
        ...

    def commit(self, writes: Sequence[Write]) -> None:
        ...

    def collections(self) -> list[str]:
        ...
