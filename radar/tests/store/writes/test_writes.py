from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from radar.adapters.firestore import layout, store
from radar.adapters.firestore.repository import StoreChangeLog
from radar.domain.model.history.ids import keyed
from radar.domain.validation.context import InvalidChangeset
from radar.tests.store import stores

FX = stores.fixture()

def _json(docs: Any, path: str) -> Any:
    return json.loads(docs.get(path)["json"])

def test_public_docs_equal_the_file_read_model() -> None:
    docs, _ = FX.seeded()
    for f in sorted((FX.public / "products").glob("*.json")):
        assert _json(docs, f"{layout.PRODUCTS}/{f.stem}") == json.loads(f.read_text(encoding="utf-8"))
    for f in sorted((FX.public / "categories").glob("*/*.json")):
        page = json.loads(f.read_text(encoding="utf-8"))
        assert _json(docs, f"{layout.FACETS}/{f.parent.name}") == page["facets"]
        assert _json(docs, f"{layout.FACETS}/{f.parent.name}/{layout.PAGES}/{f.stem}") == {
            k: v for k, v in page.items() if k != "facets"}
    assert _json(docs, f"{layout.INDEX}/market") == json.loads((FX.public / "market.json").read_text(encoding="utf-8"))

def test_a_replay_rebuilds_the_live_store_byte_for_byte() -> None:
    docs, files = FX.seeded()
    claim, name, org, source = (FX.rows(f)[0]
                                for f in ("claims.jsonl", "names.jsonl", "organizations.jsonl", "sources.jsonl"))
    changed = copy.deepcopy(claim)
    changed["value"]["range"]["max"] += 40
    FX.apply(docs, files, "seq-1", stores.put(changed, "Datasheet revision B", claim["source_refs"]))
    FX.apply(docs, files, "seq-2", stores.put({**name, "value": f"{name['value']} Mk II"}, "Renamed by the vendor", []))
    product = next(p for p in FX.rows("products.jsonl") if p.get("parent"))
    role = next(r for r in FX.rows("product_org_roles.jsonl") if r["product"] == product["id"])
    new = {**product, "id": f"{product['id'][:-1]}z", "slug": f"{product['slug']}-mini"}
    FX.apply(docs, files, "seq-3", stores.put(new, "New model", role["source_refs"]),
             stores.put({**name, "id": f"{name['id'][:-1]}z", "subject": new["id"], "value": "Widget Mini"},
                        "New model", []),
             stores.put({**role, "id": f"{role['id'][:-1]}z", "product": new["id"]}, "New model", role["source_refs"]))
    FX.apply(docs, files, "seq-4", stores.put({**org, "name": f"{org['name']} Group"}, "Renamed", []))
    FX.apply(docs, files, "seq-5", stores.put({**source, "retrieved_at": "2026-10-17T09:00:00Z"}, "Read again", []))
    FX.apply(docs, files, "seq-6",
             *(stores.retract(i, "Withdrawn", role["source_refs"])
               for i in (new["id"], f"{name['id'][:-1]}z", f"{role['id'][:-1]}z")))
    event = FX.rows("lifecycle_events.jsonl")[0]
    released = {**event, "id": f"{event['id'][:-1]}b", "type": "released", "state": "actual",
                "date": {"value": "2026-01", "precision": "month"}}
    FX.apply(docs, files, "seq-8", stores.put(released, "Released", event["source_refs"]),
             stores.put({**released, "id": f"{event['id'][:-1]}a", "type": "announced"}, "Announced",
                        event["source_refs"]))
    last = [c for c in FX.rows("claims.jsonl") if "term" in c["value"]][-1]
    other = next(c["value"]["term"] for c in FX.rows("claims.jsonl") if c["spec_key"] == last["spec_key"]
                 and c["value"]["term"] != last["value"]["term"])
    FX.apply(docs, files, "seq-9",
             stores.put({**last, "id": "clm_0000000000", "value": {"term": other}, "rank": 2}, "A second term",
                        last["source_refs"]))
    used = next(r for r in FX.rows("relations.jsonl") if r["type"] == "uses_component")
    users = {r["from_entity"] for r in FX.rows("relations.jsonl")} | {used["to_entity"]}
    starts = next(p["id"] for p in FX.rows("products.jsonl") if p["id"] not in users)
    FX.apply(docs, files, "seq-10",
             stores.put({**used, "id": "rel_00000000zz", "from_entity": starts}, "Uses it", used["source_refs"]))
    FX.apply(docs, files, "seq-11", stores.retract(used["id"], "No longer uses it", used["source_refs"]))
    first = FX.versions(docs).get(claim["id"], 1)
    FX.apply(docs, files, "seq-7",
             stores.put({**first, "id": claim["id"]}, "Rollback to version 1", claim["source_refs"]))
    owned = FX.rows("org_relations.jsonl")[0]
    FX.apply(docs, files, "seq-12",
             stores.put({**{k: v for k, v in owned.items() if k != "valid_from"}, "id": "orl_00000000zz",
                        "type": "brand_of", "from_org": FX.rows("organizations.jsonl")[3]["id"]}, "A brand",
                        owned["source_refs"]),
             stores.put({**org, "name": f"{org['name']} Group", "country": "FR"}, "Moved", []))
    assert _json(docs, f"{layout.INDEX}/registry")["data_as_of"] == "2026-10-17"
    target = stores.fresh()
    assert store.replay(docs, target, FX.model) > 0
    assert set(layout.PUBLIC) <= set(docs.collections())
    assert store.differences(docs, target, layout.rebuilt(FX.model.schema)) == []

def test_a_products_history_keeps_a_withdrawn_claim_across_later_writes() -> None:
    docs, files = FX.seeded()
    claim, changed = FX.revised_claim(40)
    gone = next(c for c in FX.rows("claims.jsonl") if c["subject"] == claim["subject"] and c["id"] != claim["id"])
    FX.apply(docs, files, "w-1", stores.retract(gone["id"], "Withdrawn", gone["source_refs"]))
    FX.apply(docs, files, "w-2", stores.put(changed, "Datasheet revision B", claim["source_refs"]))
    assert {v["entity"] for v in _json(docs, f"{layout.HISTORY}/{claim['subject']}")["versions"]} == {
        gone["id"], claim["id"]}
    assert store.reproject(docs, FX.model) == 0

class _Counted:
    def __init__(self, docs: Any) -> None:
        self.docs, self.read = docs, 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self.docs, name)

    def get_many(self, paths: list[str]) -> dict[str, Any]:
        found = self.docs.get_many(paths)
        self.read += sum(not p.startswith(layout.PUBLIC) for p in found)
        return found

    def where(self, collection: str, field: str, values: Any, contains: bool = False) -> list[Any]:
        found = self.docs.where(collection, field, values, contains)
        self.read += 0 if collection.startswith(layout.PUBLIC) else len(found)
        return found

def test_a_models_approval_reads_as_many_records_in_a_family_of_200_as_in_a_family_of_2() -> None:
    docs, files = FX.seeded()
    model = next(p for p in FX.rows("products.jsonl") if p.get("parent"))
    role = next(r for r in FX.rows("product_org_roles.jsonl") if r["product"] == model["id"])
    name = next(n for n in FX.rows("names.jsonl") if n["subject"] == model["id"] and n["is_primary"])

    def sibling(n: int) -> list[dict[str, Any]]:
        pid = keyed("prd", f"sibling-{n}")
        return [stores.put({**model, "id": pid, "slug": f"{model['slug']}-{n}"}, "New model", role["source_refs"]),
                stores.put({**name, "id": keyed("nam", f"sibling-{n}"), "subject": pid, "value": f"Widget {n}"},
                           "New model", []),
                stores.put({**role, "id": keyed("por", f"sibling-{n}"), "product": pid}, "New model",
                           role["source_refs"])]

    def reads(n: int) -> int:
        counted = _Counted(docs)
        FX.writer(counted, files).apply(stores.changeset(*sibling(n)), f"sibling-{n}")
        return counted.read

    second = reads(2)
    FX.apply(docs, files, "siblings", *(c for n in range(3, 200) for c in sibling(n)))
    assert reads(200) == second
    assert store.reproject(docs, FX.model) == 0

def test_a_change_that_adds_an_error_or_a_new_slug_writes_nothing() -> None:
    docs, files = FX.seeded()
    before = stores.everything(docs)
    product, claim, other = FX.rows("products.jsonl")[0], FX.rows("claims.jsonl")[0], FX.rows("products.jsonl")[1]
    source = FX.rows("sources.jsonl")[0]
    for change in (stores.put({**product, "slug": f"{product['slug']}-renamed"}, "New slug", []),
                   stores.put({**source, "id": f"{source['id'][:-1]}z"}, "Its address read twice", []),
                   stores.retract(f"{claim['id'][:-1]}z", "Gone", []),
                   stores.put({**product, "id": f"{product['id'][:-1]}z", "slug": other["slug"]}, "A slug taken", []),
                   stores.put({**claim, "subject": "prd_zzzzzzzzzz"}, "Wrong product", claim["source_refs"]),
                   stores.put({**claim, "value": {"quantity": {"value": 1.0, "unit": "mm"}}}, "No source", [])):
        with pytest.raises(InvalidChangeset):
            FX.apply(docs, files, "bad", change)
    assert stores.everything(docs) == before

def test_history_diff_and_rollback_of_a_rollback_on_the_emulators(tmp_path: Path) -> None:
    place = FX.loaded()
    claim, changed = FX.revised_claim(40)
    stores.cli(FX, place, "change", "apply",
               stores.changes_file(tmp_path, "changeset.json",
                                   stores.put(changed, "Datasheet revision B", claim["source_refs"])))
    for to, reason in (("1", "Revision B withdrawn"), ("2", "Revision B confirmed after all")):
        filed = FX.json(place, "record", "rollback", claim["id"], "--to", to, "--reason", reason)
        assert (filed["status"] == "suggested"
                and len(FX.json(place, "record", "history", claim["id"])["versions"]) == int(to) + 1)
        stores.cli(FX, place, "proposal", "approve", filed["id"], "--note", "Checked against the datasheet")
    history = FX.json(place, "record", "history", claim["id"])
    assert [v["version"] for v in history["versions"]] == [4, 3, 2, 1]
    versions = FX.versions(stores.fresh_at(place[0]))
    assert (versions.get(claim["id"], 4) == versions.get(claim["id"], 2)
            != versions.get(claim["id"], 3) == versions.get(claim["id"], 1))
    diff = FX.json(place, "record", "diff", claim["id"], "1", "4")
    assert diff == {"changes": [{"path": "value.range.max", "before": json.dumps(claim["value"]["range"]["max"]),
                                 "after": json.dumps(changed["value"]["range"]["max"])}]}
    missing = stores.cli(FX, place, "record", "rollback", claim["id"], "--to", "1", "--reason", " ", check=False)
    assert missing.returncode == 1

def test_two_writers_racing_to_one_version_leave_one() -> None:
    docs, files = FX.seeded()
    claim = FX.rows("claims.jsonl")[0]

    def change(value: float) -> dict[str, Any]:
        changed = copy.deepcopy(claim)
        changed["value"]["range"]["max"] = value
        return stores.put(changed, f"Set to {value}", claim["source_refs"])

    def race(commit: int) -> None:
        if commit == 1:
            FX.apply(docs, files, "first", change(301.0))

    with pytest.raises((ValueError, OSError)):
        FX.apply(stores.Hooked(docs, race), files, "second", change(302.0))
    log = StoreChangeLog(docs, FX.model)
    assert [(c.version, c.correlation_id) for c in log.for_entity(claim["id"]).changes][1:] == [(2, "first")]
    assert FX.stored(docs, claim["id"])["value"]["range"]["max"] == 301.0
