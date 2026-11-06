from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

from radar.domain.ai.budget import Cap, Usage, Use

class Budget(Protocol):
    def caps(self) -> Mapping[Use, Cap]:
        ...

    def usage(self, use: Use, day: str, client: str | None = None) -> Usage:
        ...

    def charge(self, use: Use, day: str, cad: float, client: str | None = None, calls: int = 1) -> None:
        ...

class Outcome(str, Enum):
    ANSWERED = "answered"
    REFUSED = "refused"
    CAPPED = "capped"
    ERROR = "error"

@dataclass(frozen=True, slots=True)
class Ended:
    outcome: Outcome
    tokens_in: int
    tokens_out: int
    reason: str | None = None
    calls: int = 1

class Unparsed(ValueError):
    def __init__(self, reason: str, tokens_in: int, tokens_out: int, cad: float = 0.0) -> None:
        super().__init__(reason)
        self.reason, self.tokens_in, self.tokens_out, self.cad = reason, tokens_in, tokens_out, cad

@dataclass(frozen=True, slots=True)
class ModelCall:
    use: Use
    prompt: str
    model: str
    tokens_in: int
    tokens_out: int
    cad: float
    latency_ms: int
    outcome: Outcome
    reason: str | None = None
    calls: int = 1

class UsageLog(Protocol):
    def record(self, call: ModelCall) -> None:
        ...
