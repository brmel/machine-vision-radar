from __future__ import annotations

import json
import struct
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Any, Mapping, Sequence

from radar.adapters.ai.search import ranking
from radar.adapters.ai.search.files import CURRENT, BlobStoreIndexFiles, json_bytes, sha256_hex
from radar.adapters.ai.search.records import Labels, Record, embedding_text, fingerprint, record_of
from radar.domain.model.entities import EmbedderModel, IndexManifest, IndexShard
from radar.domain.model.registry import Registry
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.search.embedder import Embedder
from radar.domain.ports.search.index_runs import Action
from radar.domain.ports.search.search_engine import Built, Hit, IndexMismatch, IndexState, NoIndex, SearchRequest

READERS = 8

def float16(vectors: Sequence[Sequence[float]]) -> bytes:
    return b"".join(struct.pack(f"<{len(v)}e", *v) for v in vectors)

def unfloat16(packed: bytes, dimension: int) -> list[list[float]]:
    values = struct.unpack(f"<{len(packed) // 2}e", packed)
    return [list(values[i:i + dimension]) for i in range(0, len(values), dimension)]

def _matches(manifest: IndexManifest, embedder: Embedder) -> bool:
    model = embedder.model
    return (manifest.embedder.model_id, manifest.embedder.dimension) == (model.model_id, model.dimension)

def _parse_manifest(raw: dict[str, Any]) -> IndexManifest:
    return IndexManifest(version=raw["version"], embedder=EmbedderModel(**raw["embedder"]),
                         read_model=raw["read_model"], shards=tuple(IndexShard(**s) for s in raw["shards"]),
                         products=raw["products"])

def _build_records(read_model: CatalogRepository, registry: Registry) -> tuple[
        list[Record], dict[str, str], dict[str, str]]:
    index = read_model.index()
    labels = Labels.of(index, registry)
    cards = sorted(index.products, key=lambda c: c.id)
    views = {v.id: v for v in read_model.products([c.id for c in cards])}
    records = [record_of(c, views[c.id], labels) for c in cards]
    texts = {r.id: embedding_text(r, views[r.id], labels) for r in records}
    prints = {r.id: fingerprint(r, texts[r.id])[:16] for r in records}
    return records, texts, prints

class ShardedSearch:
    def __init__(self, files: BlobStoreIndexFiles, embedder: Embedder, registry: Registry,
                 read_model: CatalogRepository) -> None:
        self._files, self._embedder, self._registry, self._config = files, embedder, registry, registry.search
        self._read_model = read_model
        self._manifest: IndexManifest | None = None

    @property
    def manifest(self) -> IndexManifest:
        if self._manifest is None:
            path = self._files.current()
            if path is None:
                raise NoIndex("no search index in this store: run `radar index rebuild`")
            self._manifest = _parse_manifest(json.loads(self._files.read(path)))
        return self._manifest

    def last_indexed(self) -> IndexState:
        manifest = self.manifest
        return IndexState(manifest.version, manifest.embedder, len(manifest.products))

    def files(self) -> set[str]:
        path = self._files.current()
        if path is None:
            return set()
        return {CURRENT, path, *(p for s in self.manifest.shards for p in (s.records, s.vectors))}

    def _read(self, paths: Sequence[str]) -> list[bytes]:
        with ThreadPoolExecutor(max_workers=READERS) as pool:
            return list(pool.map(self._files.read, paths))

    def _records(self, shards: Sequence[IndexShard]) -> list[Record]:
        return [Record.from_json(r) for body in self._read([s.records for s in shards])
                for r in json.loads(body)["records"]]

    def _vectors(self, shards: Sequence[IndexShard]) -> dict[str, list[float]]:
        bodies = self._read([p for s in shards for p in (s.records, s.vectors)])
        out: dict[str, list[float]] = {}
        for records, vectors in zip(bodies[::2], bodies[1::2]):
            ids = [r["card"]["id"] for r in json.loads(records)["records"]]
            out.update(zip(ids, unfloat16(vectors, self.manifest.embedder.dimension)))
        return out

    def _reusable(self) -> tuple[Mapping[str, str], dict[str, list[float]]]:
        try:
            manifest = self.manifest
        except NoIndex:
            return {}, {}
        if not _matches(manifest, self._embedder):
            return {}, {}
        return manifest.products, self._vectors(manifest.shards)

    def _write(self, previous: Mapping[str, str], kept: Mapping[str, list[float]]) -> Built:
        records, texts, prints = _build_records(self._read_model, self._registry)
        stale = [r.id for r in records if previous.get(r.id) != prints[r.id] or r.id not in kept]
        vectors = {**kept, **dict(zip(stale, self._embedder.embed([texts[i] for i in stale])))}
        shards = self._put_shards(records, vectors)
        manifest = {"embedder": asdict(self._embedder.model), "read_model": sha256_hex(json_bytes(prints))[:16],
                    "shards": shards, "products": prints}
        manifest["version"] = version = sha256_hex(json_bytes(manifest))[:16]
        self._files.set_current(version, self._files.put(json_bytes(manifest), ".json", "application/json"))
        self._manifest = _parse_manifest(manifest)
        return Built(version, tuple(stale), tuple(sorted(set(previous) - set(prints))), len(records))

    def _put_shards(self, records: Sequence[Record], vectors: Mapping[str, list[float]]) -> list[dict[str, Any]]:
        by_category: dict[str, list[Record]] = defaultdict(list)
        for r in records:
            by_category[r.category].append(r)
        files = {c: (json_bytes({"category": c, "records": [r.to_json() for r in by_category[c]]}),
                     float16([vectors[r.id] for r in by_category[c]]))
                 for c in sorted(by_category)}
        return [{"category": c, "records": self._files.put(body, ".json", "application/json"),
                 "vectors": self._files.put(weights, ".f16", "application/octet-stream"),
                 "count": len(by_category[c]), "bytes": len(body) + len(weights)}
                for c, (body, weights) in files.items()]

    def index(self, action: Action) -> Built:
        return self._write({}, {}) if action == "rebuild" else self._write(*self._reusable())

    def search(self, request: SearchRequest) -> list[Hit]:
        shards = [s for s in self.manifest.shards if request.category is None or s.category == request.category]
        records = [r for r in self._records(shards) if request.tag is None or request.tag in r.card.tags]
        keyword_hits = ranking.keyword(records, request.query, self._config)
        if keyword_hits and not request.semantic:
            return keyword_hits[:request.limit]
        if not _matches(self.manifest, self._embedder):
            built, model = self.manifest.embedder, self._embedder.model
            raise IndexMismatch(f"the index was built with {built.model_id} ({built.dimension} dimensions) and the "
                                "registry's model is "
                                f"{model.model_id} ({model.dimension}): run `radar index rebuild`")
        query_vector = self._embedder.embed([request.query])[0]
        semantic_hits = ranking.semantic(records, self._vectors(shards), query_vector, self._config.semantic_threshold)
        return ranking.blend(keyword_hits, semantic_hits, self._config.rrf_k)[:request.limit]
