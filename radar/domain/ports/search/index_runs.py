from __future__ import annotations

from typing import Literal, Protocol

from radar.domain.model.entities import IndexRunView

Action = Literal["update", "rebuild"]

class IndexRuns(Protocol):
    def record(self, run: IndexRunView) -> None:
        ...

    def latest(self, limit: int) -> list[IndexRunView]:
        ...
