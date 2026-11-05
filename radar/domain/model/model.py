from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, TypeVar

from .entities import CLASSES
from .registry import Registry
from .schema import FieldSpec, ModelSchema, TypeSpec, variant_class

type Json = None | bool | int | float | str | list[Json] | dict[str, Json]
T = TypeVar("T")

class ParseError(ValueError):
    ...

def _describe(raw: Json) -> str:
    return ("null" if raw is None
            else {dict: "object", list: "array", str: "string", bool: "boolean"}.get(type(raw), type(raw).__name__))

class Parser:
    def __init__(self, schema: ModelSchema) -> None:
        self._schema = schema

    def parse(self, raw: Json, kind: type[T], path: str) -> T:
        return kind(**self._fields(raw, self._schema.types[kind.__name__], path))

    def _fields(self, raw: Json, spec: TypeSpec, path: str) -> dict[str, object]:
        if not isinstance(raw, dict):
            raise ParseError(f"{path}: expected {spec.name} object, got {_describe(raw)}")
        unknown = sorted(set(raw) - {f.name for f in spec.fields})
        if unknown:
            raise ParseError(f"{path}: unknown field(s) {unknown} for {spec.name}")
        kwargs: dict[str, object] = {}
        for f in spec.fields:
            if f.name not in raw:
                if not f.optional:
                    raise ParseError(f"{path}: missing required field '{f.name}' of {spec.name}")
                continue
            kwargs[f.name] = self._field(raw[f.name], f, f"{path}.{f.name}")
        return kwargs

    def _field(self, raw: Json, f: FieldSpec, path: str) -> object:
        if f.type == "enum":
            return _member(raw, f.values, path)
        if f.type == "array":
            if not isinstance(raw, list):
                raise ParseError(f"{path}: expected array of {f.leaf_type}, got {_describe(raw)}")
            if len(raw) < f.min_items:
                raise ParseError(f"{path}: needs at least {f.min_items} item(s)")
            return tuple(self._value(x, f.leaf_type, f"{path}[{i}]") for i, x in enumerate(raw))
        if f.type == "map":
            return self._map(raw, f.leaf_type, path, None, ())
        out = self._value(raw, f.type, path)
        if f.minimum is not None and isinstance(out, (int, float)) and out < f.minimum:
            raise ParseError(f"{path}: must be at least {f.minimum:g}, got {out}")
        return out

    def _value(self, raw: Json, type_name: str, path: str) -> object:
        if type_name in _PRIMITIVES:
            return _primitive(raw, type_name, path)
        spec = self._schema.types[type_name]
        if spec.kind == "scalar":
            return _scalar(raw, spec, path)
        if spec.kind == "enum":
            return _member(raw, spec.values, path)
        if spec.kind == "map":
            out = self._map(raw, spec.items or "string", path, spec.key_pattern, spec.required_keys, spec.name)
            for k, v in out.items():
                if spec.min_length and len(str(v).strip()) < spec.min_length:
                    raise ParseError(f"{path}.{k}: {spec.name} text must not be empty")
            return out
        if spec.kind == "union":
            return self._union(raw, spec, path)
        return self.parse(raw, CLASSES[type_name], path)

    def _map(self, raw: Json, item: str, path: str, key_pattern: str | None, required: tuple[str, ...],
             name: str = "map") -> Mapping[str, object]:
        if not isinstance(raw, dict):
            raise ParseError(f"{path}: expected {name} object, got {_describe(raw)}")
        for k in required:
            if k not in raw:
                raise ParseError(f"{path}: {name} requires key '{k}'")
        if key_pattern:
            for k in raw:
                if not re.fullmatch(key_pattern, k):
                    raise ParseError(f"{path}: invalid {name} key {k!r}")
        return MappingProxyType({k: self._value(v, item, f"{path}.{k}") for k, v in raw.items()})

    def _union(self, raw: Json, spec: TypeSpec, path: str) -> object:
        tags = [v.name for v in spec.variants]
        if not isinstance(raw, dict) or len(raw) != 1 or next(iter(raw)) not in tags:
            raise ParseError(f"{path}: expected {spec.name} as an object with exactly one of {tags}, got {raw!r}")
        tag, inner = next(iter(raw.items()))
        variant = next(v for v in spec.variants if v.name == tag)
        return CLASSES[variant_class(spec.name, tag)](**{tag: self._field(inner, variant, f"{path}.{tag}")})

_PRIMITIVES = {"string": (str,), "boolean": (bool,), "integer": (int,), "number": (int, float)}

def _primitive(raw: Json, type_name: str, path: str) -> Json:
    kinds = _PRIMITIVES[type_name]
    if not isinstance(raw, kinds) or (isinstance(raw, bool) and bool not in kinds):
        raise ParseError(f"{path}: expected {type_name}, got {_describe(raw)}")
    return raw

def _member(raw: Json, values: tuple[str, ...], path: str) -> Json:
    if raw not in values:
        raise ParseError(f"{path}: expected one of {list(values)}, got {raw!r}")
    return raw

def _scalar(raw: Json, spec: TypeSpec, path: str) -> Json:
    out = _primitive(raw, spec.base or "string", f"{path} ({spec.name})")
    if spec.pattern and isinstance(out, str) and not re.fullmatch(spec.pattern, out):
        raise ParseError(f"{path}: {out!r} is not a valid {spec.name}")
    return out

@dataclass(frozen=True, slots=True)
class Model:
    schema: ModelSchema
    registry: Registry

    def parse(self, raw: Json, kind: type[T], where: str = "") -> T:
        return Parser(self.schema).parse(raw, kind, where or kind.__name__)
