from __future__ import annotations

import copy
import functools
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import jsonschema
import pytest

from radar import paths
from radar.adapters.files import json_store
from radar.adapters.files.blob_files import kept_path
from radar.adapters.files.model_json import load_model
from radar.adapters.firestore import layout, store
from radar.adapters.firestore.docs import FirestoreDocs
from radar.adapters.firestore.repository import StoreChangeLog, StoreProposalQueue, StoreVersionStore
from radar.domain.model.history.changeset import Changeset, parse_changeset
from radar.domain.ports.store.docs import Docs, Fields, Write
from radar.adapters.firestore.writer import StoreWriter
from radar.adapters.ai.search.engine import ShardedSearch
from radar.adapters.ai.search.fastembed_embedder import FastembedEmbedder
from radar.adapters.ai.search.files import BlobStoreIndexFiles
from radar.adapters.storage.blobs import StorageBlobStore
from radar.domain.model.entities import Document
from radar.domain.model.history.projection import plain
from radar.domain.model.model import Model
from radar.domain.read_model.derived.identity import ProductIdentity
from radar.domain.review.agents.duplicates import HELD
from radar.domain.review.review import Review
from radar.tests.fixtures.fixture_category import FilesCatalogRepository, built

FIRESTORE, STORAGE = os.environ.get("FIRESTORE_EMULATOR_HOST"), os.environ.get("FIREBASE_STORAGE_EMULATOR_HOST")
PROJECT = "demo-mvradar"
NOW = "2026-10-18T12:00:00Z"

def status(method: str, url: str, token: str | None = None, body: dict | None = None) -> int:
    headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})}
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status
    except urllib.error.HTTPError as exc:
        return exc.code

def need_emulators() -> None:
    if FIRESTORE and STORAGE:
        return
    if os.environ.get("MVR_EMULATOR_GATE"):
        pytest.fail("the emulator gate runs without the Firestore and Storage emulators")
    pytest.skip("needs the Firestore and Storage emulators (npm run check starts them)")

def fresh() -> FirestoreDocs:
    return fresh_at(place()[0])

def fresh_at(database: str) -> FirestoreDocs:
    need_emulators()
    return FirestoreDocs(f"http://{FIRESTORE}/v1", PROJECT, database=database)

def objects(bucket: str) -> list[str]:
    names, token = [], ""
    while True:
        query = urllib.parse.urlencode({"pageToken": token} if token else {})
        req = urllib.request.Request(f"http://{STORAGE}/v0/b/{bucket}/o?{query}",
                                     headers={"Authorization": "Bearer owner"})
        with urllib.request.urlopen(req) as res:
            page = json.loads(res.read())
        names += [i["name"] for i in page.get("items", [])]
        token = page.get("nextPageToken", "")
        if not token:
            return sorted(names)

def place() -> tuple[str, str]:
    name = f"t-{uuid.uuid4().hex[:12]}"
    return name, f"{name}.appspot.com"

def blobs() -> StorageBlobStore:
    need_emulators()
    return StorageBlobStore(f"http://{STORAGE}", f"t-{uuid.uuid4().hex[:12]}.appspot.com")

@dataclass(frozen=True)
class Fixture:
    out: Path
    model: Model
    records: list[dict[str, Any]]
    media: dict[str, store.Media]

    @property
    def public(self) -> Path:
        return self.out / "dist" / "public"

    @functools.cached_property
    def read(self) -> FilesCatalogRepository:
        return FilesCatalogRepository(self.public, self.model)

    @functools.cached_property
    def index(self) -> dict[str, Any]:
        return plain(self.read.index())

    @functools.cached_property
    def search_engine(self) -> ShardedSearch:
        engine = ShardedSearch(BlobStoreIndexFiles(blobs()), FastembedEmbedder(self.model.registry.search.model),
                               self.model.registry, self.read)
        engine.index("rebuild")
        return engine

    @functools.cached_property
    def views(self) -> list[dict[str, Any]]:
        return [plain(self.read.product(c["id"])) for c in self.index["products"]]

    def rows(self, name: str) -> list[dict[str, Any]]:
        return [json.loads(line) for line in (self.out / "data" / name).read_text(encoding="utf-8").splitlines()]

    def env(self, place: tuple[str, str]) -> dict[str, str]:
        return {**os.environ, "MVR_DATA": str(self.out), "MVR_FIREBASE_PROJECT": PROJECT,
                "MVR_FIRESTORE_DATABASE": place[0], "MVR_STORAGE_BUCKET": place[1]}

    def wire(self, place: tuple[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.env(place).items():
            monkeypatch.setenv(key, value)
        monkeypatch.setattr(paths, "REGISTRY", self.out / "registry")

    def load_cli(self) -> tuple[str, ...]:
        return ("store", "load", str(self.out / "data"), "--blobs", str(self.out / "blobs"))

    def load(self, docs: Docs, files: Any, cid: str = "load-test") -> dict[str, int]:
        return store.load(docs, files, self.model, self.records, self.media, cid, NOW)

    def seeded(self) -> tuple[FirestoreDocs, StorageBlobStore]:
        docs, files = fresh(), blobs()
        self.load(docs, files)
        return docs, files

    def revised_claim(self, add: float) -> tuple[dict[str, Any], dict[str, Any]]:
        claim = self.rows("claims.jsonl")[0]
        changed = copy.deepcopy(claim)
        changed["value"]["range"]["max"] += add
        return claim, changed

    def writer(self, docs: Docs, files: Any) -> StoreWriter:
        return StoreWriter(docs, self.model, lambda: NOW, files)

    def versions(self, docs: Docs) -> StoreVersionStore:
        return StoreVersionStore(docs, StoreChangeLog(docs, self.model))

    def queue(self, docs: Docs) -> StoreProposalQueue:
        return StoreProposalQueue(docs, self.model.registry.proposal_kinds())

    def review(self, docs: Docs, files: Any) -> Review:
        ticks = iter(f"2026-10-18T13:{n // 60:02d}:{n % 60:02d}Z" for n in range(3600))
        held = lambda: layout.catalog_of(self.model, store.scan(docs, self.model.schema, tuple(HELD)))
        return Review(self.queue(docs), self.writer(docs, files), self.versions(docs), held,
                      ProductIdentity.of(self.model.registry), self.model.schema, lambda: next(ticks))

    def apply(self, docs: Docs, files: Any, cid: str, *changes: dict[str, Any]) -> None:
        self.writer(docs, files).apply(changeset(*changes), cid)

    def stored(self, docs: Docs, entity_id: str) -> dict[str, Any]:
        return layout.record_of(docs.get(layout.canonical(self.model.schema, entity_id)))

    def holding(self, records: list[dict[str, Any]]) -> tuple[str, str]:
        where = place()
        store.load(fresh_at(where[0]), StorageBlobStore(f"http://{STORAGE}", where[1]), self.model, records,
                   self.media, "load-test", NOW)
        return where

    def loaded(self, *then: tuple[str, ...]) -> tuple[str, str]:
        where = place()
        for args in (self.load_cli(), *then):
            cli(self, where, *args)
        return where

    def json(self, where: tuple[str, str], *args: str) -> Any:
        return json.loads(cli(self, where, *args).stdout)

@functools.cache
def fixture() -> Fixture:
    out = built()
    model = load_model(out / "registry")
    catalog = json_store.load_catalog(out / "data", model)
    public = {k: bool(t.public) for k, t in model.registry.vocabularies["media_rights"].items()}
    media = {d.sha256: store.Media(kept_path(out / "blobs", d.sha256), d.mime, public[d.rights])
             for d in catalog.all(Document)}
    return Fixture(out, model, layout.records_of(catalog, model.schema), media)

_OPS_DOC = json.loads((paths.CONTRACTS / "operations.json").read_text(encoding="utf-8"))
OUTPUTS = {op["cli"]: {"$defs": _OPS_DOC["$defs"], **op["output"]} for op in _OPS_DOC["operations"]}

def cli(fx: Fixture, place: tuple[str, str], *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    need_emulators()
    run = subprocess.run([sys.executable, "-m", "radar", "--json", *args], cwd=paths.DEV, env=fx.env(place),
                         capture_output=True, text=True, check=check)
    if run.returncode == 0:
        noun, verb = [a for a in args if not a.startswith("-")][:2]
        jsonschema.validate(json.loads(run.stdout), OUTPUTS[f"{noun} {verb}"])
    return run

def everything(docs: Docs) -> dict[str, Fields]:
    return {p: f for c in docs.collections() for p, f in store.walk(docs, c)}

def put(record: dict[str, Any], reason: str, refs: list[str] | None = None) -> dict[str, Any]:
    return {"op": "put", "entity": {k: v for k, v in record.items() if k != "version"}, "reason": reason,
            "actor_kind": "human", "actor": "curator",
            "source_refs": record.get("source_refs", []) if refs is None else refs}

def retract(entity_id: str, reason: str, refs: list[str]) -> dict[str, Any]:
    return {"op": "retract", "id": entity_id, "reason": reason, "actor_kind": "human", "actor": "curator",
            "source_refs": refs}

def changeset(*changes: dict[str, Any]) -> Changeset:
    return parse_changeset({"changes": list(changes)})

def file(tmp_path: Path, name: str, body: Any) -> str:
    (tmp_path / name).write_text(json.dumps(body), encoding="utf-8")
    return str(tmp_path / name)

def changes_file(tmp_path: Path, name: str, *changes: dict[str, Any]) -> str:
    return file(tmp_path, name, {"changes": list(changes)})

class Hooked:
    def __init__(self, docs: Docs, hook: Callable[[int], None]) -> None:
        self._docs, self._hook, self._commits = docs, hook, 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._docs, name)

    def commit(self, writes: Sequence[Write]) -> None:
        self._commits += 1
        self._hook(self._commits)
        self._docs.commit(writes)
