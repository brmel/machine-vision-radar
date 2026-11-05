from __future__ import annotations

import hashlib
import urllib.parse
from pathlib import Path

import pytest

from radar.adapters.files import json_store
from radar.adapters.firestore import layout, store
from radar.domain.ports.store.docs import Put
from radar.adapters.storage.blobs import StorageBlobStore, media_path
from radar.adapters.firestore.ledgers import COLLECTIONS
from radar.domain.ports.store.blob_store import BlobRef
from radar.tests.store import stores

FX = stores.fixture()

def test_media_get_and_url_through_the_cli(tmp_path: Path) -> None:
    place = FX.loaded()
    public = next(sha for sha, m in FX.media.items() if m.public)
    private = next(sha for sha, m in FX.media.items() if not m.public)
    out = tmp_path / "got"
    stores.cli(FX, place, "media", "get", public, "--out", str(out))
    assert hashlib.sha256(out.read_bytes()).hexdigest() == public
    assert FX.json(place, "media", "url", public)["url"].endswith(
        urllib.parse.quote(media_path(public, FX.media[public].mime), safe="") + "?alt=media")
    refused = stores.cli(FX, place, "media", "url", private, check=False)
    assert refused.returncode == 1 and "has no URL" in refused.stderr
    StorageBlobStore(f"http://{stores.STORAGE}", place[1]).write(
        media_path(public, FX.media[public].mime), b"tampered", FX.media[public].mime, True)
    assert stores.cli(FX, place, "media", "get", public, "--out", str(out), check=False).returncode == 1

def test_backup_then_restore_reproduces_every_collection() -> None:
    place = FX.loaded()
    manifest = FX.json(place, "store", "backup")
    restored = f"{place[0]}-restored"
    stores.cli(FX, place, "store", "restore", manifest["instant"], "--into", restored)
    live, back = stores.fresh_at(place[0]), stores.fresh_at(restored)
    assert sorted(back.collections()) == sorted(live.collections()) == sorted(manifest["collections"])
    assert store.differences(live, back, live.collections()) == []
    again = stores.cli(FX, place, "store", "restore", manifest["instant"], "--into", restored, check=False)
    assert again.returncode == 1 and "empty store" in again.stderr

def test_export_writes_the_catalog_folder_that_loads_back_equal(tmp_path: Path) -> None:
    place, out, schema = FX.loaded(), tmp_path / "store", FX.model.schema
    out.mkdir()
    (out / "gone.jsonl").write_text("{}\n", encoding="utf-8")
    counts = FX.json(place, "store", "export", str(out))["counts"]
    assert sorted(p.stem for p in out.glob("*.jsonl")) == sorted(counts)
    events = f"{layout.changes_prefix(schema)}_"
    exported, given = ([r for r in layout.records_of(json_store.load_catalog(d, FX.model), schema)
                        if not r["id"].startswith(events)] for d in (out, FX.out / "data"))
    assert exported == given
    refilled = (f"{place[0]}-refilled", place[1])
    stores.cli(FX, refilled, "store", "load", str(out), "--blobs", str(FX.out / "blobs"))
    live = stores.fresh_at(place[0])
    assert store.differences(live, stores.fresh_at(refilled[0]), live.collections()) == []

def test_a_rights_change_moves_the_files_visibility_with_it() -> None:
    docs, files = FX.seeded()
    document = next(d for d in FX.rows("documents.jsonl") if FX.media[d["sha256"]].public)
    private = next(k for k, t in FX.model.registry.vocabularies["media_rights"].items() if not t.public)
    url = files.url(BlobRef(document["sha256"], document["mime"]), True)
    assert stores.status("GET", url) == 200
    for rights, readable in ((private, False), (document["rights"], True)):
        record = {k: v for k, v in document.items() if k != "version"} | {"rights": rights}
        FX.apply(docs, files, f"rights-{rights}", stores.put(record, "Rights checked", []))
        assert stores.status("GET", url) == (200 if readable else 403)

def test_a_purge_lists_then_deletes_only_what_nothing_reads() -> None:
    docs, files = FX.seeded()
    docs.commit([Put("research_queue/a", {"subject": "prd_0000000001"}), Put("public_search/1", {"json": "{}"}),
                 Put("changes/chg_gone000001", {"entity": "gone_0000000001"}),
                 Put("versions/gone_0000000001/v/1", {"id": "gone_0000000001"})])
    for instant in ("20260101T000000Z", "20260102T000000Z"):
        store.backup(docs, files, instant)
    for name in ("managed-exports/all_namespaces/export.json", "index/current.json", "index/blobs/live.json",
                 "index/blobs/stale.json", "media/zz/stray.pdf"):
        files.write(name, b"{}", "application/json")
    found = store.purgeable(docs, files, FX.model.schema, {"index/current.json", "index/blobs/live.json"})
    assert found.collections == {"public_search": 1, "research_queue": 1}
    assert found.orphans == ("changes/chg_gone000001", "versions/gone_0000000001/v/1")
    assert {n.split("/")[0] + "/" + n.split("/")[1] for n in found.objects} == {
        "backups/20260101T000000Z", "index/blobs"}
    assert "index/blobs/stale.json" in found.objects and "index/blobs/live.json" not in found.objects
    assert store.purge(docs, files, found) == 4 + len(found.objects)
    assert store.purgeable(docs, files, FX.model.schema,
                           {"index/current.json", "index/blobs/live.json"}) == store.Purge({}, (), {})
    names = {n for n, _ in files.sizes()}
    assert {"managed-exports/all_namespaces/export.json", "index/blobs/live.json", "media/zz/stray.pdf"} <= names
    assert any(n.startswith("backups/20260102T000000Z/") for n in names)
    assert all(files.has(BlobRef(d["sha256"], d["mime"])) for d in FX.rows("documents.jsonl"))

def test_store_purge_keeps_the_review_queue_the_ask_ledger_and_the_live_index() -> None:
    place = FX.loaded(("index", "rebuild"), ("store", "backup"))
    live = [f"{c}/kept" for c in (layout.PROPOSALS, layout.LOG, layout.FEED_STATE, *COLLECTIONS)]
    docs = stores.fresh_at(place[0])
    docs.commit([Put(p, {"id": "kept"}) for p in (*live, "stray/1")])
    listed = FX.json(place, "store", "purge")
    assert (listed["collections"], listed["orphans"], listed["objects"], listed["deleted"]) == ({"stray": 1}, [], [], 0)
    assert FX.json(place, "store", "purge", "--apply")["deleted"] == 1
    assert [p for p in (*live, "stray/1") if docs.get(p) is None] == ["stray/1"]
