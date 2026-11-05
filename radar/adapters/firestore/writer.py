from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Collection, Mapping, Sequence

from radar.adapters.files.json_parser import ParseError
from radar.domain.model.history.ids import keyed
from radar.domain.model.history.projection import plain
from radar.domain.model.registry import Registry
from radar.domain.model.schema import FieldSpec, ModelSchema
from radar.domain.ports.store.blob_store import BlobRef, BlobStore
from radar.domain.model.entities import ActorKind
from radar.domain.model.changeset import Applied, Change, Changeset, EntityChange, PutEntity, Retract, without_version
from radar.domain.validation.context import Finding, InvalidChangeset, ValidationContext
from radar.domain.validation.runner import validate
from radar.domain.ports.store.docs import BATCH, Delete, Docs, Fields, Put
from .layout import CHANGES, Record, canonical, canonical_doc, catalog_of, changes_prefix, read_records, version
from .projection.neighborhood import Changed, Neighborhood, ReferenceGraph
from .projection.projector import Projector

Clock = Callable[[], str]
Writes = Mapping[str, Fields | None]

def commit(docs: Docs, writes: Writes, create: Collection[str] = ()) -> int:
    paths = sorted(writes)
    stored = docs.get_many(paths)
    ops = [Put(p, writes[p], p in create) if writes[p] is not None else Delete(p) for p in paths
           if stored.get(p) != writes[p]]
    done = 0
    try:
        for done in range(0, len(ops), BATCH):
            docs.commit(ops[done:done + BATCH])
    except Exception:
        undo = [Put(o.path, stored[o.path]) if o.path in stored else Delete(o.path) for o in ops[:done]]
        for start in range(0, len(undo), BATCH):
            docs.commit(undo[start:start + BATCH])
        raise
    return len(ops)

def patch(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[Record]:
    text = lambda v: json.dumps(v, ensure_ascii=False)
    ops = [{"op": "add" if k not in before else "replace", "path": k, "value": text(v)} for k, v in after.items()
           if before.get(k) != v]
    return ops + [{"op": "remove", "path": k} for k in before if k not in after]

def change_id(prefix: str, entity: str, n: int) -> str:
    return keyed(prefix, f"{entity}:{n}")

def counted(schema: ModelSchema) -> set[str]:
    return {e.name for e in schema.entities if e.collection != CHANGES
            and any(f.name == "version" and f.type == "integer" for f in e.fields)}

def event(entity: str, n: int, before: Mapping[str, Any] | None, after: Mapping[str, Any] | None, *, change_id: str,
          recorded_at: str, actor_kind: str, actor: str, reason: str, source_refs: Sequence[str], correlation_id: str,
          proposal: str | None = None) -> Record:
    return {"id": change_id, "entity": entity, "version": n, "recorded_at": recorded_at, "actor_kind": actor_kind,
            "actor": actor, "reason": reason, "patch": patch(without_version(before), without_version(after)),
            "source_refs": list(source_refs), "correlation_id": correlation_id,
            **({"proposal": proposal} if proposal else {})}

def snapshots(entity: str, n: int, after: Mapping[str, Any] | None) -> dict[str, Fields]:
    return {version(entity, n): {"json": json.dumps(without_version(after), ensure_ascii=False, separators=(",", ":"),
                                                    sort_keys=True)}}

def _unparsed(schema: ModelSchema, record: Record) -> Finding | None:
    try:
        catalog_of(schema, [record])
    except (ParseError, KeyError) as exc:
        return Finding("record_parse", record["id"], f"does not parse: {exc}")
    return None

def _let_go(record: Record, f: FieldSpec, entity: str) -> PutEntity | Retract:
    kept = [x for x in record[f.name] if x != entity] if f.type == "array" else []
    if kept:
        return PutEntity({**record, f.name: kept})
    if f.optional:
        return PutEntity({k: v for k, v in record.items() if k != f.name})
    return Retract(record["id"])

@dataclass(frozen=True, slots=True)
class Planned:
    changed: dict[str, tuple[Record | None, Record | None]]
    events: list[Record]

    def changes(self) -> tuple[EntityChange, ...]:
        return tuple(EntityChange(i, without_version(b) or None, without_version(a) or None)
                     for i, (b, a) in self.changed.items())

class StoreWriter:
    def __init__(self, docs: Docs, schema: ModelSchema, registry: Registry, clock: Clock, blobs: BlobStore) -> None:
        self.docs, self.schema, self.registry, self.clock, self.blobs = docs, schema, registry, clock, blobs
        self.graph, self.projector = ReferenceGraph(docs, schema), Projector(docs, schema, registry)
        self.changes, self.counted = changes_prefix(schema), counted(schema)
        self.public = registry.marked("media_rights", lambda t: t.public)

    def _next(self, entity: str, before: Record | None) -> int:
        if before:
            return before.get("version", 0) + 1
        return max((f["version"] for _, f in self.docs.where(CHANGES, "entity", [entity])), default=0) + 1

    def _stored(self, ids: list[str]) -> dict[str, Record]:
        if len(set(ids)) != len(ids) or any(i.startswith(f"{self.changes}_") for i in ids):
            raise InvalidChangeset(["a changeset changes each entity once, and never a Change event"])
        try:
            return read_records(self.docs, self.schema, ids)
        except ValueError as exc:
            raise InvalidChangeset([str(exc)]) from exc

    def plan(self, changeset: Changeset, correlation_id: str) -> Planned:
        stored = self._stored([c.entity for c in changeset.changes])
        now, changed, events = self.clock(), {}, []
        for c in changeset.changes:
            before = stored.get(c.entity)
            body = dict(c.action.record) if isinstance(c.action, PutEntity) else None
            if before is None and body is None:
                raise InvalidChangeset([f"{c.entity}: no such record to retract"])
            if without_version(before) == (body or {}):
                continue
            self._slug_free(c.entity, before, body)
            n = self._next(c.entity, before)
            versioned = body is not None and self.schema.kind_of(c.entity) in self.counted
            changed[c.entity] = (before, {**body, "version": n} if versioned else body)
            events.append(event(c.entity, n, before, body, change_id=change_id(self.changes, c.entity, n),
                                recorded_at=now, actor_kind=c.actor_kind, actor=c.actor, reason=c.reason,
                                source_refs=c.source_refs, correlation_id=correlation_id, proposal=c.proposal))
        return Planned(changed, events)

    def _slug_free(self, entity: str, before: Record | None, body: Record | None) -> None:
        if body is None or "slug" not in body:
            return
        if before is not None and body["slug"] != before.get("slug"):
            raise InvalidChangeset([f"{entity}: a published slug never changes ({before.get('slug')})"])
        taken = [f["id"]
                 for _, f in self.docs.where(canonical(self.schema, entity).split("/")[0], "slug", [body["slug"]])
                 if f["id"] != entity]
        if taken:
            raise InvalidChangeset([f"{entity}: slug '{body['slug']}' belongs to {taken[0]}"])

    def _visibility(self, changed: Changed) -> list[tuple[BlobRef, bool]]:
        out = []
        for before, after in changed.values():
            if after is None or "sha256" not in after or "rights" not in after:
                continue
            ref, public = BlobRef(after["sha256"], after["mime"]), after["rights"] in self.public
            if not self.blobs.has(ref):
                raise InvalidChangeset([f"{after['id']}: no stored file {ref.sha256}; add it first (radar media add)"])
            if before is None or (before.get("rights") in self.public) != public:
                out.append((ref, public))
        return out

    def _validate(self, hood: Neighborhood, changed: Changed, today: date) -> None:
        if unparsed := [f for _, after in changed.values() if after and (f := _unparsed(self.schema, after))]:
            raise InvalidChangeset(unparsed)
        try:
            results = [validate(ValidationContext(catalog_of(self.schema, records.values()), self.registry, self.schema,
                                                  today)).errors
                       for records in (hood.records, hood.after(changed))]
        except (ParseError, KeyError) as exc:
            raise InvalidChangeset([f"a stored record of its neighborhood does not parse: {exc}"]) from exc
        records = hood.records.keys() | changed.keys()
        added = sorted((f for f in set(results[1]) - set(results[0]) if f.entity_id in records),
                       key=lambda f: (f.entity_id, f.rule, f.message))
        if added:
            raise InvalidChangeset(added)

    def _checked(self, planned: Planned) -> tuple[Changed, Neighborhood]:
        changed: Changed = {**planned.changed, **{e["id"]: (None, e) for e in planned.events}}
        hood = self.graph.neighborhood(changed)
        self._validate(hood, changed, date.fromisoformat(planned.events[0]["recorded_at"][:10]))
        return changed, hood

    def withdrawal(self, entity: str, reason: str, actor_kind: ActorKind, actor: str) -> Changeset:
        out: dict[str, Change] = {entity: Change(Retract(entity), reason, actor_kind, actor, ())}
        for f, named in self.graph.naming(entity):
            r = without_version(named)
            out[r["id"]] = Change(_let_go(r, f, entity), reason, actor_kind, actor, tuple(r.get("source_refs", ())))
        return Changeset(tuple(out.values()))

    def preview(self, changeset: Changeset) -> tuple[EntityChange, ...]:
        stored = self._stored([c.entity for c in changeset.changes])
        after = {c.entity: dict(c.action.record) if isinstance(c.action, PutEntity) else None
                 for c in changeset.changes}
        return tuple(EntityChange(i, without_version(stored.get(i)) or None, a) for i, a in after.items()
                     if without_version(stored.get(i)) != (a or {}))

    def check(self, changeset: Changeset) -> tuple[EntityChange, ...]:
        planned = self.plan(changeset, "check")
        if planned.changed:
            self._checked(planned)
            self._visibility(planned.changed)
        return planned.changes()

    def apply(self, changeset: Changeset, correlation_id: str) -> Applied:
        planned = self.plan(changeset, correlation_id)
        if not planned.changed:
            return Applied((), 0)
        changed, hood = self._checked(planned)
        visibility = self._visibility(planned.changed)
        writes: dict[str, Fields | None] = {canonical(self.schema, i): canonical_doc(a) if a is not None else None
                                            for i, (_, a) in changed.items()}
        for e in planned.events:
            writes.update(snapshots(e["entity"], e["version"], planned.changed[e["entity"]][1]))
        writes.update(self.projector.writes(hood, changed))
        for ref, public in visibility:
            self.blobs.publish(ref, public)
        try:
            written = commit(self.docs, writes, {canonical(self.schema, e["id"]) for e in planned.events})
        except Exception:
            for ref, public in visibility:
                self.blobs.publish(ref, not public)
            raise
        self._remove_withdrawn(planned.changed)
        parsed = catalog_of(self.schema, planned.events)
        return Applied(tuple(plain(parsed.get(e["id"])) for e in planned.events), written)

    def _remove_withdrawn(self, changed: Changed) -> None:
        for before, after in changed.values():
            if after is None and before and "sha256" in before:
                kind = canonical(self.schema, before["id"]).split("/")[0]
                if not self.docs.where(kind, "sha256", [before["sha256"]]):
                    self.blobs.remove(BlobRef(before["sha256"], before["mime"]))
