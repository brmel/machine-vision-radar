from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest

from radar import paths
from radar.adapters.files.blob_files import kept_path
from radar.adapters.firestore import layout
from radar.domain.ports.store.docs import Put
from radar.domain.ports.store.blob_store import BlobRef
from radar.domain.validation.rules.catalog import category_and_roles
from radar.tests.store import stores

FX = stores.fixture()

def test_load_writes_every_entity_event_snapshot_and_file() -> None:
    docs, files = stores.fresh(), stores.blobs()
    written = FX.load(docs, files)
    recorded = FX.rows("changes.jsonl")
    entities = [r for r in FX.records if not r["id"].startswith(f"{layout.changes_prefix(FX.model.schema)}_")]
    imported = [r for r in entities if r["id"] not in {c["entity"] for c in recorded}]
    for e in FX.model.schema.entities:
        rows = FX.rows(f"{e.collection}.jsonl") if (FX.out / "data" / f"{e.collection}.jsonl").exists() else []
        assert written.get(e.collection, 0) == len(rows) + (len(imported) if e.collection == layout.CHANGES else 0), (
            e.collection)
    assert written[layout.VERSIONS] == len(imported) + len(recorded)
    assert (len(FX.media) == len(FX.rows("documents.jsonl"))
            and all(files.has(BlobRef(sha, m.mime)) for sha, m in FX.media.items()))

def test_the_cli_refuses_to_load_into_a_store_that_holds_anything() -> None:
    run = stores.cli(FX, FX.loaded(), *FX.load_cli(), check=False)
    assert run.returncode == 1 and "load writes into an empty store" in run.stderr

def _claims_cite_nothing(out: Path) -> None:
    broken = out / "data" / "claims.jsonl"
    rows = [json.loads(line) for line in broken.read_text().splitlines()]
    broken.write_text("".join(json.dumps({**r, "source_refs": ["src_zzzzzzzzzz"]}) + "\n" for r in rows))

def _document(out: Path, row: int, **fields: Any) -> None:
    held = out / "data" / "documents.jsonl"
    rows = [json.loads(line) for line in held.read_text().splitlines()]
    rows[row].update(fields)
    held.write_text("".join(json.dumps(r) + "\n" for r in rows))

def _kept(out: Path) -> Path:
    first = json.loads((out / "data" / "documents.jsonl").read_text().splitlines()[0])
    return kept_path(out / "blobs", first["sha256"])

def _twice(out: Path) -> None:
    held = out / "data" / "documents.jsonl"
    first = json.loads(held.read_text().splitlines()[0])
    held.write_text(held.read_text() + json.dumps({**first, "id": "doc_00000000zz"}) + "\n")

@pytest.mark.parametrize(("broken", "why"), [
    (_claims_cite_nothing, "src_zzzzzzzzzz"),
    (lambda out: _document(out, 0, mime="image/png"), "does not fit kind"),
    (lambda out: _document(out, 0, width=640, height=480), "width/height belong to images and videos only"),
    (lambda out: _document(out, 1, duration=3.5), "duration belongs to videos only"),
    (lambda out: _document(out, 0, sha256="not-a-digest"), "invalid sha256"),
    (lambda out: _document(out, 0, bytes=99), "not 99 bytes"),
    (lambda out: _kept(out).write_bytes(b"tampered"), "the kept file hashes to"),
    (lambda out: _kept(out).unlink(), "no kept file for sha256"),
    (lambda out: (out / "blobs" / "ee").mkdir() or (out / "blobs" / "ee" / f"{'e' * 62}.pdf").write_bytes(b"x"),
     "has no Document"),
    (_twice, "is also held by doc_00000000zz")])
def test_the_cli_validates_first_and_writes_nothing_on_an_error(
        tmp_path: Path, broken: Callable[[Path], object], why: str) -> None:
    shutil.copytree(FX.out, tmp_path / "fx")
    broken(tmp_path / "fx")
    fx = stores.Fixture(tmp_path / "fx", FX.model, FX.records, FX.media)
    place = stores.place()
    run = stores.cli(fx, place, *fx.load_cli(), check=False)
    assert run.returncode == 1 and "nothing written" in run.stderr and why in run.stderr
    assert stores.fresh_at(place[0]).collections() == []

def test_store_validate_catches_a_slug_two_records_of_a_kind_share() -> None:
    place = FX.loaded()
    kinds: dict[str, list[dict[str, Any]]] = {}
    for r in FX.records:
        if "slug" in r:
            kinds.setdefault(FX.model.schema.kind_of(r["id"]) or "", []).append(r)
    first, second = next(rows for rows in kinds.values() if len(rows) > 1)[:2]
    docs, path = stores.fresh_at(place[0]), layout.canonical(FX.model.schema, second["id"])
    docs.commit([Put(path, {**(docs.get(path) or {}), "slug": first["slug"]})])
    run = stores.cli(FX, place, "store", "validate", check=False)
    assert run.returncode == 1 and f".slug '{first['slug']}' is also held by" in run.stderr

def test_load_backup_and_index_write_exactly_the_documented_layout() -> None:
    place = FX.loaded(("store", "backup"), ("index", "rebuild"))
    written = [*sorted(stores.everything(stores.fresh_at(place[0]))), *stores.objects(place[1])]
    section = (paths.DEV / "docs" / "SYSTEM.md").read_text(encoding="utf-8").split("## 1.")[1].split("## 2.")[0]
    rows = [line for line in section.splitlines() if line.startswith(("| `", "| Storage `"))]
    entity = "|".join(e.collection for e in FX.model.schema.entities if e.collection)
    patterns = {d: re.compile("".join(f"(?:{entity})" if p == "<collection>" else "[^/]+" if p.startswith("{")
                                      else re.escape(p) for p in re.split(r"(\{[^}]+\}|<collection>)", d)))
                for row in rows for d in re.findall(r"`([^`]+)`", row.split("|")[1])}
    unmatched = [p for p in written if not any(r.fullmatch(p) for r in patterns.values())]
    unused = [d for d, r in patterns.items() if not any(r.fullmatch(p) for p in written)]
    assert unmatched == [] and unused == []

def test_reproject_writes_back_only_the_public_docs_that_differ_and_drops_the_gone() -> None:
    place = FX.loaded()
    docs = stores.fresh_at(place[0])
    product = next(p for p, _ in docs.list(layout.PRODUCTS))
    canonical = dict(docs.list("products"))
    docs.commit([Put(product, {"json": "{}"}), Put(f"{layout.PRODUCTS}/prd_zzzzzzzzzz", {"json": "{}"})])
    first = FX.json(place, "store", "reproject")
    assert (first["written"] == 2 and docs.get(f"{layout.PRODUCTS}/prd_zzzzzzzzzz") is None
            and json.loads(docs.get(product)["json"])["id"])
    assert dict(docs.list("products")) == canonical
    assert FX.json(place, "store", "reproject")["written"] == 0

def test_the_json_fields_stay_out_of_the_indexes() -> None:
    indexes = paths.CONTRACTS / "firebase" / "firestore.indexes.json"
    overrides = json.loads(indexes.read_text(encoding="utf-8"))["fieldOverrides"]
    unindexed = {(o["collectionGroup"], o["fieldPath"]) for o in overrides if o["indexes"] == []}
    assert unindexed == {*((c, "json") for c in (*layout.PUBLIC, layout.PAGES, layout.SNAPSHOTS)),
                         (layout.PRODUCTS, "card")}

def test_every_log_line_and_event_of_a_run_carries_its_correlation_id(tmp_path: Path) -> None:
    place = stores.place()
    loaded = stores.cli(FX, place, *FX.load_cli())
    _, claim = FX.revised_claim(5)
    ranked = {**stores.put(claim, "Ranked below the newer datasheet"), "actor_kind": "agent", "actor": "ranker"}
    change = stores.cli(FX, place, "change", "apply", "--json", stores.changes_file(tmp_path, "changeset.json", ranked))
    docs = stores.fresh_at(place[0])
    recorded = {c["entity"] for c in FX.rows("changes.jsonl")} | {c["id"] for c in FX.rows("changes.jsonl")}
    for run, expected in ((loaded, len([r for r in FX.records if r["id"] not in recorded])), (change, 1)):
        lines = [json.loads(line) for line in run.stderr.splitlines()]
        cid = json.loads(run.stdout)["correlation_id"]
        assert lines and {line["correlation_id"] for line in lines} == {cid}
        events = docs.where(layout.CHANGES, "correlation_id", [cid])
        assert len(events) == expected and {f["correlation_id"] for _, f in events} == {cid}

def test_store_validate_counts_each_kind_it_read() -> None:
    place = stores.place()
    moved = FX.json(place, *FX.load_cli())["docs"]
    report = FX.json(place, "store", "validate")
    kinds = set(layout.collections(FX.model.schema).values())
    assert (report["ok"] and report["errors"] == []
            and category_and_roles.NAME in {w["rule"] for w in report["warnings"]})
    assert report["counts"] == {c: n for c, n in moved.items() if c in kinds} != {}
