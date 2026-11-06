from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Iterator, Mapping, Sequence

from radar.domain.model.catalog import MemoryCatalog
from radar.domain.model.entities import CLASSES, Change as Event, Entity
from radar.domain.model.history.changeset import (CHANGESET, Change, Changeset, EntityChange, PutEntity, Retract,
                                                  as_record, put_of, without_version)
from radar.domain.model.history.ids import keyed
from radar.domain.model.schema import FieldSpec, Json, ModelSchema
from radar.domain.validation.verdict import Finding

if TYPE_CHECKING:
    from radar.domain.model.model import Model

STORED_FILE = "stored_file"
Changed = Mapping[str, tuple[Entity | None, Entity | None]]

@dataclass(frozen=True, slots=True)
class Stamp:
    recorded_at: str
    correlation_id: str

@dataclass(frozen=True, slots=True)
class Held:
    catalog: MemoryCatalog
    last: Mapping[str, int]
    kept: frozenset[str]
    unparsed: tuple[Finding, ...]

def _record(entity: Entity | None) -> dict[str, object] | None:
    return as_record(entity) if entity else None

def _changes(changed: Changed) -> tuple[EntityChange, ...]:
    return tuple(EntityChange(i, _record(b), _record(a)) for i, (b, a) in changed.items())

@dataclass(frozen=True, slots=True)
class Plan:
    changed: Changed
    events: tuple[Event, ...]

    @property
    def changes(self) -> tuple[EntityChange, ...]:
        return _changes(self.changed)

@dataclass(frozen=True, slots=True)
class Refused:
    findings: tuple[Finding, ...]
    changes: tuple[EntityChange, ...] = ()

@dataclass(frozen=True, slots=True)
class Draft:
    changed: Changed
    events: tuple[dict[str, Json], ...]

    def refused(self, findings: Sequence[Finding]) -> Refused:
        return Refused(tuple(findings), _changes(self.changed))

    def after(self, held: Held, events: Sequence[Event]) -> MemoryCatalog:
        return held.catalog.changed({**{i: a for i, (_, a) in self.changed.items()}, **{e.id: e for e in events}})

    def unkept(self, kept: frozenset[str]) -> Finding | None:
        for after in (as_record(a) for _, a in self.changed.values() if a):
            if "sha256" in after and "rights" in after and after["sha256"] not in kept:
                return Finding(STORED_FILE, str(after["id"]),
                               f"no stored file {after['sha256']}; add it first (radar media add)")
        return None

def patch(before: Mapping[str, object], after: Mapping[str, object]) -> list[Json]:
    def text(v: object) -> str:
        return json.dumps(v, ensure_ascii=False)
    ops: list[Json] = [{"op": "add" if k not in before else "replace", "path": k, "value": text(v)}
                       for k, v in after.items() if before.get(k) != v]
    return ops + [{"op": "remove", "path": k} for k in before if k not in after]

def change_id(prefix: str | None, entity: str, n: int) -> str:
    return keyed(prefix, f"{entity}:{n}")

def event(entity: str, n: int, before: Mapping[str, object] | None, after: Mapping[str, object] | None, *,
          change_id: str, recorded_at: str, actor_kind: str, actor: str, reason: str, source_refs: Sequence[str],
          correlation_id: str, proposal: str | None = None) -> dict[str, Json]:
    return {"id": change_id, "entity": entity, "version": n, "recorded_at": recorded_at, "actor_kind": actor_kind,
            "actor": actor, "reason": reason, "patch": patch(without_version(before), without_version(after)),
            "source_refs": list(source_refs), "correlation_id": correlation_id,
            **({"proposal": proposal} if proposal else {})}

def _malformed(schema: ModelSchema, ids: Sequence[str]) -> Finding | None:
    counts, events = Counter(ids), schema.types[Event.__name__].prefix
    if twice := [i for i in ids if counts[i] > 1 or i.startswith(f"{events}_")]:
        return Finding(CHANGESET, twice[0], "a changeset changes each entity once, and never a Change event")
    if unknown := [i for i in ids if not schema.kind_of(i)]:
        return Finding(CHANGESET, unknown[0], "names no entity kind")
    return None

def drafted(schema: ModelSchema, held: Held, changeset: Changeset, stamp: Stamp) -> Draft | Refused:
    if wrong := _malformed(schema, [c.entity for c in changeset.changes]):
        return Refused((wrong,))
    prefix = schema.types[Event.__name__].prefix
    changed: dict[str, tuple[Entity | None, Entity | None]] = {}
    events: list[dict[str, Json]] = []
    for c in changeset.changes:
        before = held.catalog.get(c.entity)
        after = c.action.entity if isinstance(c.action, PutEntity) else None
        if before is None and after is None:
            return Refused((Finding(CHANGESET, c.entity, "no such record to retract"),))
        if _record(before) == _record(after):
            continue
        n = (before.version if before else held.last.get(c.entity, 0)) + 1
        changed[c.entity] = (before, replace(after, version=n) if after else None)
        events.append(event(c.entity, n, _record(before), _record(after), change_id=change_id(prefix, c.entity, n),
                            recorded_at=stamp.recorded_at, actor_kind=c.actor_kind, actor=c.actor, reason=c.reason,
                            source_refs=c.source_refs, correlation_id=stamp.correlation_id, proposal=c.proposal))
    return Draft(changed, tuple(events))

def added(before: MemoryCatalog, after: MemoryCatalog, found: Sequence[Sequence[Finding]]) -> list[Finding]:
    ids = {e.id for e in (*before, *after)}
    return sorted((f for f in set(found[1]) - set(found[0]) if f.entity_id in ids),
                  key=lambda f: (f.entity_id, f.rule, f.message))

def _names(value: object, entity: str) -> bool:
    return value == entity or isinstance(value, list) and entity in value

def _naming(schema: ModelSchema, held: Held, entity: str) -> Iterator[tuple[FieldSpec, dict[str, object]]]:
    kind = schema.kind_of(entity)
    fields = [(t.name, f) for t in schema.entities if t.name != Event.__name__ for f in t.fields if kind in f.refs]
    for name, f in fields:
        for named in held.catalog.all(CLASSES[name]):
            if _names(as_record(named).get(f.name), entity):
                yield f, as_record(named)

def _let_go(model: Model, record: Mapping[str, object], f: FieldSpec, entity: str) -> PutEntity | Retract:
    value = record[f.name]
    kept = [x for x in value if x != entity] if isinstance(value, list) else []
    if kept:
        return put_of({**record, f.name: kept}, model)
    if f.optional:
        return put_of({k: v for k, v in record.items() if k != f.name}, model)
    return Retract(str(record["id"]))

def withdrawal(model: Model, held: Held, entity: str, reason: str) -> Changeset:
    out = {entity: Change(Retract(entity), reason)}
    for f, named in _naming(model.schema, held, entity):
        refs = named.get("source_refs")
        out[str(named["id"])] = Change(_let_go(model, named, f, entity), reason,
                                       source_refs=tuple(str(r) for r in refs) if isinstance(refs, list) else ())
    return Changeset(tuple(out.values()))
