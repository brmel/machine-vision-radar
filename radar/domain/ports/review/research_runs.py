from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Protocol

from radar.domain.model.entities import ResearchStatus as Status, ResearchStep as Step

@dataclass(frozen=True, slots=True)
class Line:
    at: str
    step: Step
    detail: str

Ending = Literal[Status.DONE, Status.PARTIAL, Status.BLOCKED, Status.CAPPED, Status.CANCELLED, Status.FAILED]

@dataclass(frozen=True, slots=True)
class Outcome:
    status: Ending
    reason: str
    at: str

@dataclass(frozen=True, slots=True)
class ResearchRun:
    id: str
    scope: str
    actor: str
    started_at: str
    token: str
    cad: float = 0.0
    lines: tuple[Line, ...] = ()
    outcome: Outcome | None = None

    def said(self, *steps: Step) -> tuple[str, ...]:
        return tuple(line.detail for line in self.lines if line.step in steps)

    def logged(self, line: Line) -> ResearchRun:
        return replace(self, lines=(*self.lines, line))

@dataclass(frozen=True, slots=True)
class RunPage:
    runs: tuple[ResearchRun, ...]
    cursor: str | None
    total: int

class ResearchRunLog(Protocol):
    def save(self, run: ResearchRun) -> None:
        ...

    def cancel(self, run_id: str, at: str) -> None:
        ...

    def get(self, run_id: str) -> ResearchRun:
        ...

    def page(self, cursor: str | None = None) -> RunPage:
        ...
