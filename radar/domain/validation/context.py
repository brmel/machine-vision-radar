from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from ..model.registry import Registry
from ..model.schema import ModelSchema
from ..ports.catalog.catalog import Catalog

@dataclass(frozen=True, slots=True)
class Finding:
    rule: str
    entity_id: str
    message: str

class InvalidChangeset(ValueError):
    def __init__(self, findings: Sequence[Finding | str]) -> None:
        self.findings = tuple(findings)
        super().__init__("; ".join(f if isinstance(f, str) else f"{f.rule} {f.entity_id}: {f.message}"
                                   for f in self.findings))

@dataclass(slots=True)
class ValidationResult:
    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, rule: str, entity_id: str, message: str) -> None:
        self.errors.append(Finding(rule, entity_id, message))

    def warn(self, rule: str, entity_id: str, message: str) -> None:
        self.warnings.append(Finding(rule, entity_id, message))

@dataclass(frozen=True, slots=True)
class KeptFile:
    sha256: str
    bytes: int
    mime: str

@dataclass(frozen=True, slots=True)
class ValidationContext:
    catalog: Catalog
    registry: Registry
    schema: ModelSchema
    today: date
    kept_files: Mapping[str, KeptFile] | None = None
    whole_catalog: bool = False
