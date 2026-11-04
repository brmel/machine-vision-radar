from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from radar.domain.model.entities import Change

@dataclass(frozen=True, slots=True)
class ChangePage:
    changes: tuple[Change, ...]
    cursor: str | None

class ChangeLog(Protocol):
    def for_entity(self, entity: str, cursor: str | None = None) -> ChangePage:
        ...

    def after(self, cursor: str | None = None) -> ChangePage:
        ...
