from __future__ import annotations

from typing import Protocol, Sequence, TypeVar

from radar.domain.model.entities import Claim, ProductVersion, VersionRange

T = TypeVar("T")

class Catalog(Protocol):
    def all(self, kind: type[T]) -> Sequence[T]:
        ...

    def get(self, entity_id: str) -> object | None:
        ...

    def versions_of(self, product: str) -> Sequence[ProductVersion]:
        ...

    def resolve(self, vrange: VersionRange) -> Sequence[ProductVersion]:
        ...

    def claims_for(self, subject: str) -> Sequence[Claim]:
        ...
