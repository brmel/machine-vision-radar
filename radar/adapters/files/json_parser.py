from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from radar.domain.ai.eval import DatasheetCase
from radar.domain.model import entities
from radar.domain.model.catalog import MemoryCatalog
from radar.domain.ports.ai.datasheet_extractor import Datasheet
from radar.domain.model.model import Model, ParseError

T = TypeVar("T")

def refuse_constant(name: str) -> float:
    raise ParseError(f"non-finite number {name} is not allowed")

def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=refuse_constant)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON in {path}: {exc}") from exc

def parse_catalog(raw: Any, model: Model) -> MemoryCatalog:
    if not isinstance(raw, dict):
        raise ParseError(f"expected a top-level object of collections, got {type(raw).__name__}")
    collections = {e.collection: entities.CLASSES[e.name] for e in model.schema.entities}
    unknown = sorted(set(raw) - set(collections))
    if unknown:
        raise ParseError(f"unknown top-level key(s) {unknown}; expected some of {sorted(collections)}")
    out: list[entities.Entity] = []
    for name, items in raw.items():
        if not isinstance(items, list):
            raise ParseError(f"{name}: expected an array")
        for i, item in enumerate(items):
            label = item.get("id", i) if isinstance(item, dict) else i
            out.append(model.parse(item, collections[name], f"{name}[{label}]"))
    return MemoryCatalog(out)

def parse_datasheet_set(raw: Any, model: Model) -> tuple[DatasheetCase, ...]:
    cases = raw.get("cases") if isinstance(raw, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ParseError('a datasheet set is {"cases": [...]} with at least one case')
    out = []
    for n, case in enumerate(cases):
        if not isinstance(case, dict) or not all(isinstance(case.get(k), str) for k in ("id", "product", "text")):
            raise ParseError(f"cases[{n}]: id, product and text are strings")
        expected = parse_catalog(case.get("expected"), model)
        sources = expected.all(entities.Source)
        if len(sources) != 1:
            raise ParseError(f"cases[{n}]: expected holds the datasheet's one Source")
        out.append(DatasheetCase(case["id"],
                                 Datasheet(case["product"], case["text"].encode(), "text/plain", sources[0]),
                                 tuple(expected.all(entities.Claim))))
    return tuple(out)

def load_catalog_file(path: Path, model: Model) -> MemoryCatalog:
    return parse_catalog(read_json(path), model)

class Checker:
    def __init__(self, model: Model) -> None:
        self._model = model

    def parse(self, raw: Any, view_type: type[T], where: str) -> T:
        return self._model.parse(raw, view_type, where)
