from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Collection, Iterable, Mapping

from radar.domain.model.catalog import MemoryCatalog
from radar.domain.model.entities import CLASSES, Entity
from radar.domain.model.history.changeset import RECORD_PARSE, Changeset, PutEntity, as_record, without_version
from radar.domain.model.history.plan import Held, Plan
from radar.domain.model.history.projection import plain
from radar.domain.model.model import Model, ParseError
from radar.domain.ports.store.blob_store import BlobRef, BlobStore
from radar.domain.ports.store.docs import BATCH, Delete, Docs, Fields, Put
from radar.domain.validation.verdict import Finding
from .layout import CHANGES, Record, canonical, canonical_doc, read_records, version
from .projection.neighborhood import Changed, Neighborhood, ReferenceGraph
from .projection.projector import Projector

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

def snapshots(entity: str, n: int, after: Mapping[str, Any] | None) -> dict[str, Fields]:
    return {version(entity, n): {"json": json.dumps(without_version(after), ensure_ascii=False, separators=(",", ":"),
                                                    sort_keys=True)}}

def _parsed(model: Model, records: Iterable[Record]) -> tuple[list[Entity], tuple[Finding, ...]]:
    entities, unparsed = [], []
    for r in sorted(records, key=lambda r: r["id"]):
        kind = model.schema.kind_of(r["id"]) or ""
        try:
            entities.append(model.parse(r, CLASSES[kind], f"{model.schema.collection(kind)}[{r['id']}]"))
        except (ParseError, KeyError) as exc:
            unparsed.append(Finding(RECORD_PARSE, r["id"], f"does not parse: {exc}"))
    return entities, tuple(unparsed)

def _changing(changeset: Changeset, stored: Mapping[str, Record]) -> dict[str, tuple[Record | None, Record | None]]:
    changing: dict[str, tuple[Record | None, Record | None]] = {}
    for c in changeset.changes:
        after = as_record(c.action.entity) if isinstance(c.action, PutEntity) else None
        if without_version(stored.get(c.entity)) != (after or {}):
            changing[c.entity] = (stored.get(c.entity), after)
    return changing

@dataclass(frozen=True, slots=True)
class StoreHeld(Held):
    hood: Neighborhood

class FirestoreCatalogStore:
    def __init__(self, docs: Docs, model: Model, blobs: BlobStore) -> None:
        self.docs, self.model, self.schema, self.blobs = docs, model, model.schema, blobs
        self.graph, self.projector = ReferenceGraph(docs, model.schema), Projector(docs, model)
        self.public = model.registry.marked("media_rights", lambda t: t.public)

    def _last(self, ids: list[str]) -> dict[str, int]:
        last: dict[str, int] = {}
        for _, f in self.docs.where(CHANGES, "entity", ids):
            last[f["entity"]] = max(last.get(f["entity"], 0), f["version"])
        return last

    def _kept(self, changed: Changed) -> frozenset[str]:
        return frozenset(a["sha256"] for _, a in changed.values() if a and "sha256" in a and "rights" in a
                         and self.blobs.has(BlobRef(a["sha256"], a["mime"])))

    def around(self, changeset: Changeset) -> StoreHeld:
        ids = [c.entity for c in changeset.changes if self.schema.kind_of(c.entity)]
        stored = read_records(self.docs, self.schema, ids)
        changing = _changing(changeset, stored)
        cited = {r for c in changeset.changes if c.entity in changing for r in c.source_refs}
        hood = self.graph.neighborhood(changing, cited) if changing else Neighborhood({}, frozenset(), frozenset())
        entities, unparsed = _parsed(self.model, {**stored, **hood.records}.values())
        return StoreHeld(MemoryCatalog(entities), self._last([i for i in ids if i not in stored]),
                         self._kept(changing), unparsed, hood)

    def _visibility(self, changed: Changed) -> list[tuple[BlobRef, bool]]:
        out = []
        for before, after in changed.values():
            if after is None or "sha256" not in after or "rights" not in after:
                continue
            public = after["rights"] in self.public
            if before is None or (before.get("rights") in self.public) != public:
                out.append((BlobRef(after["sha256"], after["mime"]), public))
        return out

    def write(self, held: StoreHeld, plan: Plan) -> int:
        if not plan.changed:
            return 0
        changed: Changed = {i: (plain(b), plain(a)) for i, (b, a) in plan.changed.items()}
        events = {e.id: plain(e) for e in plan.events}
        everything: Changed = {**changed, **{i: (None, e) for i, e in events.items()}}
        writes: dict[str, Fields | None] = {canonical(self.schema, i): canonical_doc(a) if a is not None else None
                                            for i, (_, a) in everything.items()}
        for e in plan.events:
            writes.update(snapshots(e.entity, e.version, changed[e.entity][1]))
        writes.update(self.projector.writes(held.hood, everything))
        written = self._commit(writes, {canonical(self.schema, i) for i in events}, self._visibility(changed))
        self._remove_withdrawn(changed)
        return written

    def _commit(self, writes: Writes, create: Collection[str], visibility: list[tuple[BlobRef, bool]]) -> int:
        for ref, public in visibility:
            self.blobs.publish(ref, public)
        try:
            return commit(self.docs, writes, create)
        except Exception:
            for ref, public in visibility:
                self.blobs.publish(ref, not public)
            raise

    def _remove_withdrawn(self, changed: Changed) -> None:
        for before, after in changed.values():
            if after is None and before and "sha256" in before:
                kind = canonical(self.schema, before["id"]).split("/")[0]
                if not self.docs.where(kind, "sha256", [before["sha256"]]):
                    self.blobs.remove(BlobRef(before["sha256"], before["mime"]))
