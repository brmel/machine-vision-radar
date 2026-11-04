from __future__ import annotations

from typing import Iterable

from radar.domain.model.entities import Change
from radar.domain.model.history.projection import later, paged
from radar.domain.ports.history.change_log import ChangePage

class MemoryChangeLog:
    def __init__(self, changes: Iterable[Change] = ()) -> None:
        self._changes = list(changes)

    def for_entity(self, entity: str, cursor: str | None = None) -> ChangePage:
        return paged((c for c in self._changes if c.entity == entity), cursor)

    def after(self, cursor: str | None = None) -> ChangePage:
        return later(self._changes, cursor)
