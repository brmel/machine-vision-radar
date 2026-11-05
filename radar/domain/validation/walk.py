from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Iterator, TypeVar

from ..model.entities import CLASSES, Entity
from ..model.schema import FieldSpec, ModelSchema
from ..ports.catalog.catalog import Catalog
from .context import ValidationContext

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class Visit:
    entity: Entity
    path: str
    spec: FieldSpec
    value: object

    @property
    def items(self) -> tuple[object, ...]:
        return tuple(self.value) if isinstance(self.value, tuple) else (self.value,)

def entities(catalog: Catalog, schema: ModelSchema) -> Iterator[Entity]:
    for spec in schema.entities:
        yield from catalog.all(CLASSES[spec.name])

def visits(ctx: ValidationContext) -> Iterator[Visit]:
    for e in entities(ctx.catalog, ctx.schema):
        yield from _record(ctx.schema, e, e, type(e).__name__, type(e).__name__)

def _record(schema: ModelSchema, entity: Entity, obj: object, type_name: str, path: str) -> Iterator[Visit]:
    for f in schema.types[type_name].fields:
        value = getattr(obj, f.name)
        if value is not None:
            yield from _field(schema, entity, f, value, f"{path}.{f.name}")

def _field(schema: ModelSchema, entity: Entity, f: FieldSpec, value: object, path: str) -> Iterator[Visit]:
    yield Visit(entity, path, f, value)
    inner = schema.types.get(f.leaf_type)
    if inner is None or inner.kind in ("scalar", "map"):
        return
    if f.type == "map":
        items: list[tuple[str, object]] = [(f"{path}.{k}", v) for k, v in value.items()]
    elif f.type == "array":
        items = [(f"{path}[{i}]", v) for i, v in enumerate(value)]
    else:
        items = [(path, value)]
    for p, v in items:
        yield from _value(schema, entity, f.leaf_type, v, p)

def _value(schema: ModelSchema, entity: Entity, type_name: str, value: object, path: str) -> Iterator[Visit]:
    spec = schema.types[type_name]
    if spec.kind == "record":
        yield from _record(schema, entity, value, type_name, path)
    elif spec.kind == "union":
        for variant in spec.variants:
            inner = getattr(value, variant.name, None)
            if inner is not None:
                yield from _field(schema, entity, variant, inner, f"{path}.{variant.name}")

def repeated(keys: Iterable[T]) -> list[tuple[T, int]]:
    return [(key, n) for key, n in Counter(keys).items() if n > 1]
