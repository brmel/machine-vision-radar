from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from ..model.registry import Registry
from ..model.schema import ModelSchema
from ..ports.catalog.catalog import Catalog

@dataclass(frozen=True, slots=True)
class Whole:
    ...

@dataclass(frozen=True, slots=True)
class Part:
    ...

Scope = Whole | Part

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
    scope: Scope
    kept_files: Mapping[str, KeptFile] | None = None
