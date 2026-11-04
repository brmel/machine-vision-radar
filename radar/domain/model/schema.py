from __future__ import annotations

from dataclasses import dataclass, field, fields as fields_of
from typing import Any, Literal, Mapping, Sequence

PRIMITIVES = ("string", "number", "integer", "boolean")
CONTAINERS = ("array", "map", "enum")
Kind = Literal["scalar", "enum", "map", "record", "union", "entity"]

def variant_class(union: str, tag: str) -> str:
    return union + "".join(p.capitalize() for p in tag.split("_"))

class SchemaError(ValueError):
    ...

@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    type: str
    items: str | None = None
    values: tuple[str, ...] = ()
    optional: bool = False
    vocabulary: str | None = None
    key_vocabulary: str | None = None
    refs: tuple[str, ...] = ()
    min_items: int = 0
    minimum: float | None = None
    future_allowed: bool = False
    set_on_approval: bool = False
    unique: bool = False
    description: str | None = None
    label: Mapping[str, str] | None = None
    default: Any = None
    format: str | None = None

    @property
    def leaf_type(self) -> str:
        return self.items if self.type in ("array", "map") and self.items else self.type

@dataclass(frozen=True, slots=True)
class TypeSpec:
    name: str
    kind: Kind
    description: str
    fields: tuple[FieldSpec, ...] = ()
    base: str | None = None
    pattern: str | None = None
    key_pattern: str | None = None
    required_keys: tuple[str, ...] = ()
    items: str | None = None
    values: tuple[str, ...] = ()
    min_length: int = 0
    variants: tuple[FieldSpec, ...] = ()
    prefix: str | None = None
    collection: str | None = None
    internal: bool = False
    registry_file: str | None = None
    label: Mapping[str, str] | None = None
    provenance: Literal["source", "file"] | None = None

@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    input: TypeSpec
    output: str
    title: str
    read_only: bool
    destructive: bool

@dataclass(frozen=True, slots=True)
class ModelSchema:
    types: Mapping[str, TypeSpec]
    value_types: tuple[TypeSpec, ...] = field(default=())
    registry_types: tuple[TypeSpec, ...] = field(default=())
    entities: tuple[TypeSpec, ...] = field(default=())
    views: tuple[TypeSpec, ...] = field(default=())
    tools: tuple[Tool, ...] = field(default=())

    def used_by_views(self) -> tuple[TypeSpec, ...]:
        used: set[str] = set()
        todo = [f.leaf_type for v in self.views for f in (*v.fields, *v.variants)]
        while todo:
            name = todo.pop()
            t = self.types.get(name)
            if name in used or t in (None, *self.views):
                continue
            used.add(name)
            todo += [f.leaf_type for f in (*t.fields, *t.variants)] + ([t.items] if t.items else [])
        return tuple(t for t in self.value_types if t.name in used)

    def reference_paths(self, type_name: str, prefix: str = "", seen: frozenset[str] = frozenset()) -> list[
            tuple[str, FieldSpec]]:
        out: list[tuple[str, FieldSpec]] = []
        t = self.types[type_name]
        for f in (*t.fields, *t.variants):
            inner = self.types.get(f.leaf_type)
            if f.leaf_type == "EntityId" and f.name != "id":
                out.append((prefix + f.name, f))
            elif (inner and inner.kind in ("record", "union") and f.type not in ("array", "map")
                    and f.leaf_type not in seen):
                out += self.reference_paths(f.leaf_type, f"{prefix}{f.name}.", seen | {type_name})
        return out

    def vocabularies(self) -> set[str]:
        return {v for t in self.types.values() for f in (*t.fields, *t.variants)
                for v in (f.vocabulary, f.key_vocabulary) if v}

    def kind_of(self, entity_id: str) -> str | None:
        prefix, _, _ = entity_id.partition("_")
        return next((e.name for e in self.entities if e.prefix == prefix), None)

    def collection(self, kind: str) -> str:
        found = next((e.collection for e in self.entities if (e.name == kind or e.prefix == kind) and e.collection),
                     None)
        if not found:
            raise ValueError(f"unknown entity kind '{kind}'")
        return found

_FIELD_KEYS = {f.name for f in fields_of(FieldSpec)} - {"name"}
_LISTS = ("values", "refs", "required_keys")

def _field(owner: str, name: str, raw: Mapping[str, Any] | str) -> FieldSpec:
    if isinstance(raw, str):
        raw = {"type": raw}
    unknown = set(raw) - _FIELD_KEYS
    if unknown:
        raise SchemaError(f"{owner}.{name}: unknown field spec keys {sorted(unknown)}")
    return FieldSpec(name=name, **{k: tuple(v) if k in _LISTS else v for k, v in raw.items()})

def _type(raw: Mapping[str, Any], kind: Kind | None = None) -> TypeSpec:
    name = str(raw["id"])
    if raw.get("kind") == "enum" and not raw.get("values"):
        raise SchemaError(f"{name}: enum without values")
    members = {key: tuple(_field(name, n, f) for n, f in dict(raw.get(key, {})).items())
               for key in ("fields", "variants")}
    rest = {k: tuple(v) if k in _LISTS else v for k, v in raw.items() if k not in ("id", "kind", "fields", "variants")}
    return TypeSpec(name=name, kind=kind or raw.get("kind", "record"), **{"description": "", **rest, **members})

def _known(schema: ModelSchema, t: str | None, where: str) -> None:
    if t is None or (t not in PRIMITIVES and t not in schema.types):
        raise SchemaError(f"{where}: unknown type '{t}'")

def _check_field(schema: ModelSchema, f: FieldSpec, where: str) -> None:
    if f.type in ("array", "map"):
        _known(schema, f.items, where)
    elif f.type == "enum":
        if not f.values:
            raise SchemaError(f"{where}: enum without values")
    else:
        _known(schema, f.type, where)
    for r in f.refs:
        if r not in schema.types or schema.types[r].kind != "entity":
            raise SchemaError(f"{where}: refs names unknown entity '{r}'")

def _check(schema: ModelSchema) -> None:
    prefixes: dict[str, str] = {}
    for t in schema.types.values():
        if t.kind == "scalar" and t.base not in PRIMITIVES:
            raise SchemaError(f"{t.name}: scalar base must be one of {PRIMITIVES}")
        if t.kind == "map":
            _known(schema, t.items, t.name)
        if t.kind == "entity":
            if not t.prefix or not t.collection:
                raise SchemaError(f"{t.name}: an entity declares prefix and collection")
            if t.prefix in prefixes:
                raise SchemaError(f"{t.name}: prefix '{t.prefix}' already used by {prefixes[t.prefix]}")
            prefixes[t.prefix] = t.name
        for f in (*t.fields, *t.variants):
            _check_field(schema, f, f"{t.name}.{f.name}")
    _check_tools(schema)

def _check_tools(schema: ModelSchema) -> None:
    for tool in schema.tools:
        for f in tool.input.fields:
            _check_field(schema, f, f"{tool.name}.{f.name}")
        if tool.output not in schema.types:
            raise SchemaError(f"{tool.name}: unknown output type '{tool.output}'")

ModelFile = Sequence[Mapping[str, Any]]

def parse_schema(value_types: ModelFile, registry_types: ModelFile, entities: ModelFile, views: ModelFile,
                 tools: ModelFile) -> ModelSchema:
    value_specs = tuple(map(_type, value_types))
    registry_specs = tuple(map(_type, registry_types))
    entity_specs = tuple(_type(r, "entity") for r in entities)
    view_specs = tuple(map(_type, views))
    types: dict[str, TypeSpec] = {}
    for t in (*value_specs, *registry_specs, *entity_specs, *view_specs):
        if t.name in types or t.name in PRIMITIVES or t.name in CONTAINERS:
            raise SchemaError(f"type '{t.name}' is declared twice or shadows a builtin")
        types[t.name] = t
    schema = ModelSchema(types=types, value_types=value_specs, registry_types=registry_specs, entities=entity_specs,
                         views=view_specs,
                         tools=tuple(Tool(str(r["id"]), str(r["description"]),
                                          _type({"id": r["id"], "fields": r["input"]}), str(r["output"]),
                                          str(r["title"]), bool(r["readOnlyHint"]), bool(r["destructiveHint"]))
                                     for r in tools))
    _check(schema)
    return schema
