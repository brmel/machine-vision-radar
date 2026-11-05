from __future__ import annotations

from typing import Protocol

from radar.domain.model.entities import ActorKind
from radar.domain.model.history.changeset import Applied, Changeset, EntityChange

class CatalogWriter(Protocol):
    def withdrawal(self, entity: str, reason: str, actor_kind: ActorKind, actor: str) -> Changeset:
        ...

    def preview(self, changeset: Changeset) -> tuple[EntityChange, ...]:
        ...

    def check(self, changeset: Changeset) -> tuple[EntityChange, ...]:
        ...

    def apply(self, changeset: Changeset, correlation_id: str) -> Applied:
        ...
