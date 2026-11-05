from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum

class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"

@dataclass(frozen=True, slots=True)
class Finding:
    rule: str
    entity_id: str
    message: str
    severity: Severity = Severity.ERROR

    def __str__(self) -> str:
        return f"[{self.rule}] {self.entity_id}: {self.message}"

    def report(self) -> dict[str, str]:
        return {"rule": self.rule, "entity_id": self.entity_id, "message": self.message}

Findings = Iterator[Finding]

@dataclass(frozen=True, slots=True)
class Verdict:
    findings: tuple[Finding, ...]

    @property
    def errors(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.WARNING)

    @property
    def ok(self) -> bool:
        return not self.errors

class InvalidChangeset(ValueError):
    def __init__(self, findings: Iterable[Finding]) -> None:
        self.findings = tuple(findings)
        super().__init__("; ".join(f"{f.rule} {f.entity_id}: {f.message}" for f in self.findings))
