from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal, Protocol

from radar.domain.model.entities import ResearchStatus as Status, ResearchStep as Step, RunScope

STOPPED = "its process stopped"
LABELS = "; "

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
    scope: RunScope
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

    def as_of(self, now: str, dead_after: float) -> ResearchRun:
        said = self.lines[-1].at if self.lines else self.started_at
        if self.outcome or datetime.fromisoformat(now) - datetime.fromisoformat(said) <= timedelta(seconds=dead_after):
            return self
        return replace(self.logged(Line(now, Step.ENDED, STOPPED)), outcome=Outcome(Status.FAILED, STOPPED, now))

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
