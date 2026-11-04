from __future__ import annotations

import json
import re
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeVar

from radar.domain.ai.eval import DatasheetCase
from radar.domain.model import entities
from radar.adapters.storage.memory_catalog import MemoryCatalog
from radar.domain.ports.ai.datasheet_extractor import Datasheet
from radar.domain.model.schema import FieldSpec, ModelSchema, TypeSpec, variant_class

T = TypeVar("T")

class ParseError(ValueError):
    ...

def refuse_constant(name: str) -> float:
    raise ParseError(f"non-finite number {name} is not allowed")

def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=refuse_constant)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON in {path}: {exc}") from exc

def _describe(raw: Any) -> str:
    return ("null" if raw is None
            else {dict: "object", list: "array", str: "string", bool: "boolean"}.get(type(raw), type(raw).__name__))

class ModelParser:
    def __init__(self, schema: ModelSchema) -> None:
        self._schema = schema

    def record(self, raw: Any, spec: TypeSpec, path: str) -> Any:
        if not isinstance(raw, dict):
            raise ParseError(f"{path}: expected {spec.name} object, got {_describe(raw)}")
        unknown = sorted(set(raw) - {f.name for f in spec.fields})
        if unknown:
            raise ParseError(f"{path}: unknown field(s) {unknown} for {spec.name}")
        kwargs: dict[str, Any] = {}
        for f in spec.fields:
            if f.name not in raw:
                if not f.optional:
                    raise ParseError(f"{path}: missing required field '{f.name}' of {spec.name}")
                continue
            kwargs[f.name] = self.field(raw[f.name], f, f"{path}.{f.name}")
        return getattr(entities, spec.name)(**kwargs)

    def field(self, raw: Any, f: FieldSpec, path: str) -> Any:
        if f.type == "enum":
            return _member(raw, f.values, path)
        if f.type == "array":
            if not isinstance(raw, list):
                raise ParseError(f"{path}: expected array of {f.leaf_type}, got {_describe(raw)}")
            if len(raw) < f.min_items:
                raise ParseError(f"{path}: needs at least {f.min_items} item(s)")
            return tuple(self.value(x, f.leaf_type, f"{path}[{i}]") for i, x in enumerate(raw))
        if f.type == "map":
            return self._map(raw, f.leaf_type, path, None, ())
        out = self.value(raw, f.type, path)
        if f.minimum is not None and out < f.minimum:
            raise ParseError(f"{path}: must be at least {f.minimum:g}, got {out}")
        return out

    def value(self, raw: Any, type_name: str, path: str) -> Any:
        prim = _primitive(raw, type_name, path)
        if prim is not _NOT_PRIMITIVE:
            return prim
        spec = self._schema.types[type_name]
        if spec.kind == "scalar":
            return _scalar(raw, spec, path)
        if spec.kind == "enum":
            return _member(raw, spec.values, path)
        if spec.kind == "map":
            out = self._map(raw, spec.items or "string", path, spec.key_pattern, spec.required_keys, spec.name)
            for k, v in out.items():
                if spec.min_length and len(v.strip()) < spec.min_length:
                    raise ParseError(f"{path}.{k}: {spec.name} text must not be empty")
            return out
        if spec.kind == "union":
            return self._union(raw, spec, path)
        return self.record(raw, spec, path)

    def _map(self, raw: Any, item: str, path: str, key_pattern: str | None, required: tuple[str, ...],
             name: str = "map") -> Any:
        if not isinstance(raw, dict):
            raise ParseError(f"{path}: expected {name} object, got {_describe(raw)}")
        for k in required:
            if k not in raw:
                raise ParseError(f"{path}: {name} requires key '{k}'")
        if key_pattern:
            for k in raw:
                if not re.fullmatch(key_pattern, k):
                    raise ParseError(f"{path}: invalid {name} key {k!r}")
        return MappingProxyType({k: self.value(v, item, f"{path}.{k}") for k, v in raw.items()})

    def _union(self, raw: Any, spec: TypeSpec, path: str) -> Any:
        tags = [v.name for v in spec.variants]
        if not isinstance(raw, dict) or len(raw) != 1 or next(iter(raw)) not in tags:
            raise ParseError(f"{path}: expected {spec.name} as an object with exactly one of {tags}, got {raw!r}")
        tag, inner = next(iter(raw.items()))
        variant = next(v for v in spec.variants if v.name == tag)
        cls = getattr(entities, variant_class(spec.name, tag))
        return cls(**{tag: self.field(inner, variant, f"{path}.{tag}")})

_NOT_PRIMITIVE = object()
_PRIMITIVES = {"string": (str,), "boolean": (bool,), "integer": (int,), "number": (int, float)}

def _primitive(raw: Any, type_name: str, path: str) -> Any:
    kinds = _PRIMITIVES.get(type_name)
    if kinds is None:
        return _NOT_PRIMITIVE
    if not isinstance(raw, kinds) or (isinstance(raw, bool) and bool not in kinds):
        raise ParseError(f"{path}: expected {type_name}, got {_describe(raw)}")
    return raw

def _member(raw: Any, values: tuple[str, ...], path: str) -> Any:
    if raw not in values:
        raise ParseError(f"{path}: expected one of {list(values)}, got {raw!r}")
    return raw

def _scalar(raw: Any, spec: TypeSpec, path: str) -> Any:
    out = _primitive(raw, spec.base or "string", f"{path} ({spec.name})")
    if spec.pattern and not re.fullmatch(spec.pattern, out):
        raise ParseError(f"{path}: {out!r} is not a valid {spec.name}")
    return out

def parse_catalog(raw: Any, schema: ModelSchema) -> MemoryCatalog:
    if not isinstance(raw, dict):
        raise ParseError(f"expected a top-level object of collections, got {type(raw).__name__}")
    collections = {e.collection: e for e in schema.entities}
    unknown = sorted(set(raw) - set(collections))
    if unknown:
        raise ParseError(f"unknown top-level key(s) {unknown}; expected some of {sorted(collections)}")
    parser = ModelParser(schema)
    out: list[object] = []
    for name, items in raw.items():
        if not isinstance(items, list):
            raise ParseError(f"{name}: expected an array")
        for i, item in enumerate(items):
            label = item.get("id", i) if isinstance(item, dict) else i
            out.append(parser.record(item, collections[name], f"{name}[{label}]"))
    return MemoryCatalog(out)

def parse_datasheet_set(raw: Any, schema: ModelSchema) -> tuple[DatasheetCase, ...]:
    cases = raw.get("cases") if isinstance(raw, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ParseError('a datasheet set is {"cases": [...]} with at least one case')
    out = []
    for n, case in enumerate(cases):
        if not isinstance(case, dict) or not all(isinstance(case.get(k), str) for k in ("id", "product", "text")):
            raise ParseError(f"cases[{n}]: id, product and text are strings")
        expected = parse_catalog(case.get("expected"), schema)
        sources = expected.all(entities.Source)
        if len(sources) != 1:
            raise ParseError(f"cases[{n}]: expected holds the datasheet's one Source")
        out.append(DatasheetCase(case["id"],
                                 Datasheet(case["product"], case["text"].encode(), "text/plain", sources[0]),
                                 tuple(expected.all(entities.Claim))))
    return tuple(out)

def load_catalog_file(path: Path, schema: ModelSchema) -> MemoryCatalog:
    return parse_catalog(read_json(path), schema)

class Checker:
    def __init__(self, schema: ModelSchema) -> None:
        self.schema, self.parser = schema, ModelParser(schema)

    def __call__(self, view: dict[str, Any], type_name: str, where: str) -> dict[str, Any]:
        self.parser.record(view, self.schema.types[type_name], where)
        return view

    def parse(self, raw: Any, view_type: type[T], where: str) -> T:
        return self.parser.record(raw, self.schema.types[view_type.__name__], where)
