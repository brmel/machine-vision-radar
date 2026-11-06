from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from itertools import groupby
from operator import itemgetter
from pathlib import Path
from typing import Any, Collection, Iterator, Sequence

from radar.adapters.firestore.ledgers import COLLECTIONS
from radar.adapters.storage.blobs import MEDIA, StorageBlobStore
from radar.domain.model.history.plan import change_id, event
from radar.domain.model.history.projection import states
from radar.domain.model.entities import Change
from radar.domain.model.model import Model
from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.schema import ModelSchema
from radar.domain.ports.store.blob_store import BlobStore
from . import layout
from radar.domain.ports.store.docs import BATCH, Docs, Fields, Put
from .layout import CHANGES, SUBCOLLECTIONS, Record, canonical, canonical_doc, catalog_of, changes_prefix, record_of
from .projection.projector import full
from .writer import commit, snapshots

IMPORT_ACTOR, IMPORT_REASON = "radar store load", "Loaded from a catalog folder into the store"
MANIFEST = "manifest.json"

@dataclass(frozen=True, slots=True)
class Media:
    path: Path
    mime: str
    public: bool

def projected(model: Model, records: Sequence[Record], events: Sequence[Record]) -> dict[str, Fields]:
    out: dict[str, Fields] = {canonical(model.schema, r["id"]): canonical_doc(r) for r in (*records, *events)}
    parsed = catalog_of(model, events)
    for entity, evs in groupby(events, key=itemgetter("entity")):
        for n, state in enumerate(states(parsed.get(e["id"]) for e in evs)[1:], 1):
            out.update(snapshots(entity, n, state))
    out.update(full(catalog_of(model, records), model, parsed.all(Change)))
    return out

def load(docs: Docs, blobs: BlobStore, model: Model, records: Sequence[Record], media: dict[str, Media],
         correlation_id: str, now: str) -> dict[str, int]:
    if docs.collections():
        raise ValueError("load writes into an empty store")
    prefix = changes_prefix(model.schema)
    entities = [r for r in records if not r["id"].startswith(f"{prefix}_")]
    recorded = [r for r in records if r["id"].startswith(f"{prefix}_")]
    events = [*recorded, *_imports(prefix, entities, {e["entity"] for e in recorded}, correlation_id, now)]
    wanted = projected(model, entities, sorted(events, key=lambda e: (e["entity"], e["version"])))
    for m in media.values():
        blobs.put(m.path.read_bytes(), m.mime, m.public)
    commit(docs, wanted)
    return dict(Counter(path.split("/")[0] for path in wanted))

def _imports(prefix: str, entities: Sequence[Record], changed: Collection[str], correlation_id: str,
             now: str) -> list[Record]:
    return [event(r["id"], 1, None, r, change_id=change_id(prefix, r["id"], 1), recorded_at=now, actor_kind="import",
                  actor=IMPORT_ACTOR, reason=IMPORT_REASON, source_refs=r.get("source_refs", []),
                  correlation_id=correlation_id)
            for r in entities if r["id"] not in changed]

def walk(docs: Docs, collection: str) -> Iterator[tuple[str, Fields]]:
    yield from docs.list(collection)
    if collection in SUBCOLLECTIONS:
        yield from ((p, f) for p, f in docs.group(SUBCOLLECTIONS[collection]) if p.startswith(f"{collection}/"))

def replay(source: Docs, target: Docs, model: Model) -> int:
    if target.collections():
        raise ValueError("replay writes into an empty store")
    events = sorted((f for _, f in source.list(CHANGES)), key=lambda e: (e["entity"], e["version"]))
    parsed = catalog_of(model, events)
    histories = [[parsed.get(e["id"]) for e in evs] for _, evs in groupby(events, key=itemgetter("entity"))]
    records = [{**state, "version": evs[-1].version} for evs in histories if (state := states(evs)[-1])]
    return commit(target, projected(model, records, events))

def reproject(docs: Docs, model: Model) -> int:
    records = list(scan(docs, model.schema))
    prefix = changes_prefix(model.schema)
    events = [r for r in records if r["id"].startswith(f"{prefix}_")]
    catalog = catalog_of(model, [r for r in records if not r["id"].startswith(f"{prefix}_")])
    wanted: dict[str, Fields | None] = dict(full(catalog, model, catalog_of(model, events).all(Change)))
    wanted.update({path: None for c in layout.PUBLIC for path, _ in walk(docs, c) if path not in wanted})
    return commit(docs, wanted)

def scan(docs: Docs, schema: ModelSchema, kinds: Collection[str] = ()) -> Iterator[Record]:
    for e in schema.entities:
        if e.collection and (not kinds or e.name in kinds):
            yield from (record_of(f) for _, f in docs.list(e.collection))

def backup(docs: Docs, objects: StorageBlobStore, instant: str) -> dict[str, Any]:
    counts = {}
    for c in docs.collections():
        lines = [json.dumps({"path": p, "fields": f}, ensure_ascii=False, sort_keys=True) for p, f in walk(docs, c)]
        objects.write(layout.backup(instant, f"{c}.jsonl"), "".join(f"{line}\n" for line in lines).encode(),
                      "application/x-ndjson")
        counts[c] = len(lines)
    manifest = {"instant": instant, "collections": counts}
    objects.write(layout.backup(instant, MANIFEST), json.dumps(manifest, indent=2).encode(), "application/json")
    return manifest

def restore(docs: Docs, objects: StorageBlobStore, instant: str) -> dict[str, Any]:
    if docs.collections():
        raise ValueError("restore writes into an empty store")
    manifest = json.loads(b"".join(objects.read(layout.backup(instant, MANIFEST))))
    for c in manifest["collections"]:
        rows = [json.loads(line)
                for line in b"".join(objects.read(layout.backup(instant, f"{c}.jsonl"))).decode().splitlines()]
        for start in range(0, len(rows), BATCH):
            docs.commit([Put(r["path"], r["fields"]) for r in rows[start:start + BATCH]])
    return manifest

@dataclass(frozen=True, slots=True)
class Purge:
    collections: dict[str, int]
    orphans: tuple[str, ...]
    objects: dict[str, int]

def purgeable(docs: Docs, objects: StorageBlobStore, schema: ModelSchema, index: Collection[str]) -> Purge:
    kept = {*layout.rebuilt(schema), layout.PROPOSALS, layout.LOG, layout.FEED_STATE, *COLLECTIONS}
    return Purge({c: sum(1 for _ in walk(docs, c)) for c in sorted(docs.collections()) if c not in kept},
                 _orphans(docs, schema), _stray(dict(objects.sizes()), index))

def _orphans(docs: Docs, schema: ModelSchema) -> tuple[str, ...]:
    named = [*((p, f["entity"]) for p, f in walk(docs, CHANGES)),
             *((p, p.split("/")[1]) for p, _ in walk(docs, layout.VERSIONS))]
    return tuple(p for p, entity in named if not schema.kind_of(entity))

def _stray(sizes: dict[str, int], index: Collection[str]) -> dict[str, int]:
    instants = sorted({n.split("/")[1] for n in sizes if n.startswith(f"{layout.BACKUPS}/")})
    kept = (layout.EXPORTS, MEDIA, *(f"{layout.BACKUPS}/{i}/" for i in instants[-1:]))
    return {n: size for n, size in sorted(sizes.items()) if not n.startswith(kept) and n not in index}

def purge(docs: Docs, objects: StorageBlobStore, found: Purge) -> int:
    for c in found.collections:
        commit(docs, {p: None for p, _ in walk(docs, c)})
    commit(docs, dict.fromkeys(found.orphans))
    for name in found.objects:
        objects.delete(name)
    return sum(found.collections.values()) + len(found.orphans) + len(found.objects)

def differences(a: Docs, b: Docs, collections: Sequence[str]) -> list[str]:
    out = []
    for c in collections:
        left, right = dict(walk(a, c)), dict(walk(b, c))
        out += sorted(p for p in left.keys() | right.keys() if left.get(p) != right.get(p))
    return out

class StoreCatalogs:
    def __init__(self, docs: Docs, model: Model) -> None:
        self._docs, self._model = docs, model

    def reading(self, kinds: tuple[str, ...]) -> Catalog:
        return catalog_of(self._model, scan(self._docs, self._model.schema, kinds))
