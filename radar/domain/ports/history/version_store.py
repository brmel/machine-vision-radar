from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from radar.domain.model.entities import ActorKind

@dataclass(frozen=True, slots=True)
class FieldChange:
    path: str
    before: Any
    after: Any

@dataclass(frozen=True, slots=True)
class EntityVersion:
    entity: str
    version: int
    recorded_at: str
    actor_kind: ActorKind
    actor: str
    reason: str
    source_refs: tuple[str, ...]
    proposal: str | None
    correlation_id: str
    changed: tuple[FieldChange, ...]

@dataclass(frozen=True, slots=True)
class VersionPage:
    versions: tuple[EntityVersion, ...]
    cursor: str | None
    total: int

class VersionStore(Protocol):
    def get(self, entity: str, version: int) -> dict[str, Any] | None:
        ...

    def history(self, entity: str, cursor: str | None = None) -> VersionPage:
        ...

    def diff(self, entity: str, v1: int, v2: int) -> tuple[FieldChange, ...]:
        ...
