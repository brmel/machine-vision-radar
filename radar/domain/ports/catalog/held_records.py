from __future__ import annotations

from typing import Any, Mapping, Protocol, TypeVar

from radar.domain.model.entities import Claim, Entity, Organization

T = TypeVar("T")

class HeldRecords(Protocol):
    def organizations(self) -> tuple[Organization, ...]:
        ...

    def held(self, record_id: str) -> Entity | None:
        ...

    def matching(self, kind: type[T], field: str, value: str) -> tuple[T, ...]:
        ...

    def ranked_first(self, claim: Mapping[str, Any]) -> str | None:
        ...

    def claims(self) -> tuple[Claim, ...]:
        ...

    def created_since(self, instant: str) -> frozenset[str]:
        ...
