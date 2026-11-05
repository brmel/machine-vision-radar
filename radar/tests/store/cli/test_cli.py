from __future__ import annotations

import itertools
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from radar.adapters.files import json_store
from radar.adapters.firestore.repository import StoreCatalogRepository
from radar.domain.model.history.projection import plain
from radar.domain.model.entities import OrgRelation
from radar.domain.model.dates import start_of
from radar.tests.store import stores

FX = stores.fixture()
INDEX, VIEWS = FX.index, FX.views

@pytest.fixture(scope="module")
def place() -> tuple[str, str]:
    return FX.loaded()

def _values(view: dict) -> dict[str, object]:
    return {c["key"]: c["value"] for c in (*view["core"], *view["detail"]) if "value" in c}

def test_compare_rows_follow_the_page(place: tuple[str, str]) -> None:
    a, b = next((a, b) for a, b in itertools.combinations(VIEWS, 2) if a["category"] == b["category"]
                and {k for k in set(_values(a)) & set(_values(b)) if _values(a)[k] == _values(b)[k]}
                and {k for k in set(_values(a)) & set(_values(b)) if _values(a)[k] != _values(b)[k]})
    rows = FX.json(place, "product", "compare", a["id"], b["id"])["specs"]
    values = [_values(a), _values(b)]
    assert [r["key"] for r in rows] == [c["key"] for s in ("core", "detail") for c in a[s]
                                        if any(c["key"] in v for v in values)]
    for r in rows:
        shown = [json.dumps(v.get(r["key"]), sort_keys=True) for v in values]
        assert r["diff"] == (shown[0] != shown[1]) and r["unit"] == INDEX["spec_definitions"][r["key"]].get("unit"), (
            r["key"])
    assert {r["diff"] for r in rows} == {True, False}

def test_index_search_and_eval_read_the_index_of_the_store(place: tuple[str, str]) -> None:
    run = stores.cli(FX, place, "index", "rebuild")
    built = json.loads(run.stdout)
    assert built["products"] == len(VIEWS) and len(built["embedded"]) == len(VIEWS)
    assert {json.loads(line)["correlation_id"] for line in run.stderr.splitlines()} == {built["correlation_id"]}
    assert FX.json(place, "index", "update", "--actor", "a curator")["embedded"] == []
    status = FX.json(place, "index", "status")
    assert (status["version"] == built["version"]
            and status["built_at"] == min(r["at"] for r in status["runs"] if r.get("version") == built["version"]))
    assert (status["products_indexed"], status["products_in_catalog"]) == (len(VIEWS), len(VIEWS))
    assert [(r["action"], r["actor"]) for r in status["runs"][:2]] == [("update", "a curator"), ("rebuild", "founder")]

    family = next(v for v in VIEWS if v["models"])
    for mode in ((), ("--semantic",)):
        assert FX.json(place, "product", "search", family["name"], *mode)[0]["id"] == family["id"]

    score = FX.json(place, "eval", "run", "search", "--floor", "1")
    assert score["queries"] == len(FX.rows("eval_queries.jsonl")) and score["hit_rate"] == 1.0

def test_a_change_apply_updates_the_index(tmp_path: Path) -> None:
    place = FX.loaded(("index", "rebuild"))
    product = next(r for r in FX.rows("products.jsonl") if "summary" in r)
    changed = {**{k: v for k, v in product.items() if k != "version"},
               "summary": {"en": "A widget the index must find again.", "fr": "Un widget à retrouver."}}
    run = stores.cli(FX, place, "change", "apply",
                     stores.changes_file(tmp_path, "changeset.json",
                                         stores.put(changed, "New summary", [FX.rows("sources.jsonl")[0]["id"]])))
    assert any(json.loads(line)["event"].endswith("1 embedded, 0 removed") for line in run.stderr.splitlines())
    assert FX.json(place, "product", "search", "retrouver")[0]["id"] == product["id"]

def test_a_claim_edit_shows_in_its_products_history(tmp_path: Path) -> None:
    place = FX.loaded()
    claim, changed = FX.revised_claim(40)
    read = StoreCatalogRepository(stores.fresh_at(place[0]), FX.model)
    assert (read.product(claim["subject"]).version, read.product(claim["subject"]).history) == (1, False)
    assert [(v["entity"], v["version"])
            for v in FX.json(place, "record", "history", claim["subject"])["versions"]] == [(claim["subject"], 1)]
    stores.cli(FX, place, "change", "apply",
               stores.changes_file(tmp_path, "edit.json", stores.put(changed, "Revision B")))
    assert read.product(claim["subject"]).history is True
    history = FX.json(place, "record", "history", claim["subject"])
    assert history == plain(read.history(claim["subject"]))
    assert [(v["entity"], v["version"], v.get("spec")) for v in history["versions"]] == [
        (claim["id"], 2, claim["spec_key"]), (claim["id"], 1, claim["spec_key"])]
    assert history["versions"][0]["reason"] == "Revision B" and history["versions"][0]["sources"]

def test_record_list_pages_what_the_catalog_lists(place: tuple[str, str]) -> None:
    products = FX.rows("products.jsonl")
    first = FX.json(place, "record", "list", "Product")
    rest = FX.json(place, "record", "list", "Product", "--cursor", first["next"])
    assert (len(first["records"]), first["total"], len(rest["records"]), "next" in rest) == (
        20, len(products), len(products) - 20, False)
    assert [r["id"] for r in FX.json(place, "record", "list", "Product", "--query",
                                     products[0]["id"])["records"]] == [products[0]["id"]]
    category = products[0]["category"]
    other = next(c for c in FX.model.registry.categories if c != category)
    assert FX.json(place, "record", "list", "Product", "--category", category)["total"] == sum(
        1 for p in products if p["category"] == category)
    assert FX.json(place, "record", "list", "Product", "--category", other)["records"] == []

def test_get_names_an_organizations_owners_as_they_were_named_on_a_date(place: tuple[str, str]) -> None:
    relations = list(json_store.load_catalog(FX.out / "data", FX.model).all(OrgRelation))
    first, second = sorted((r for r in relations if r.type == "acquired_by" and r.valid_from),
                           key=lambda r: start_of(r.valid_from))
    [renamed] = [r for r in relations if r.type == "renamed_from"]
    maker, owner, group = first.from_org, first.to_org, second.to_org
    on_first, on_second = start_of(first.valid_from), start_of(second.valid_from)
    owners = {day: [o["id"] for o in FX.json(place, "org", "get", maker, "--on", day.isoformat())["owners"]]
              for day in (on_first - timedelta(days=1), on_first, on_second - timedelta(days=1), on_second)}
    assert list(owners.values()) == [[], [owner], [owner], [renamed.from_org, group]]

def test_quality_market_and_export_read_the_store(place: tuple[str, str], tmp_path: Any) -> None:
    report = FX.json(place, "quality", "report")
    assert report["products"] == len(FX.rows("products.jsonl")) and report["filed"] == []
    coverage = report["coverage"]
    untagged, thin = (sorted(v["id"] for v in VIEWS if not v["tags"]),
                      sorted(v["id"] for v in VIEWS if not v["indexable"]))
    assert coverage["products"] == len(VIEWS)
    assert coverage["no_category"] == {"count": 0, "ids": []}
    assert coverage["untagged"] == {"count": len(untagged), "ids": untagged} and 0 < len(untagged) < len(VIEWS)
    assert coverage["thin"] == {"count": len(thin), "ids": thin} and thin
    assert [r["id"] for r in report["records"][:report["weak"]]] == sorted(
        r["id"] for r in report["records"] if r["weak"])
    category = VIEWS[0]["category"]
    [shares] = FX.json(place, "quality", "coverage", "--category", category)["categories"]
    members = [v for v in VIEWS if v["category"] == category]
    published = {c["key"]: sum(1 for v in members
                               if any(x["key"] == c["key"] and "value" in x for x in (*v["core"], *v["detail"])))
                 for c in (*members[0]["core"], *members[0]["detail"])}
    assert shares["products"] == len(members) and {s["key"]: s["products"] for s in shares["specs"]} == published
    stated = {(c["subject"], c["spec_key"]) for c in FX.rows("claims.jsonl")}
    required = FX.model.registry.profile(category).required
    assert shares["missing_required"] == sum(1 for v in members if any((v["id"], k) not in stated for k in required))
    assert any("none" in x.get("value", {}) for v in members for x in (*v["core"], *v["detail"])), (
        "a value stated as none counts as published")
    assert [s["products"] for s in shares["specs"]] == sorted(published.values(), reverse=True)
    assert stores.cli(FX, place, "quality", "coverage", "--category", "no.such", check=False).returncode == 2
    assert FX.json(place, "metrics", "market") == json.loads((FX.public / "market.json").read_text(encoding="utf-8"))
    stores.cli(FX, place, "site", "export", "--out", str(tmp_path))
    category = next(c for c in INDEX["categories"] if c["id"] == VIEWS[0]["category"])
    domain = next(d for d in INDEX["domains"] if d["id"] == category["domain"])
    assert domain["label"]["en"] in (tmp_path / "llms.txt").read_text(encoding="utf-8")

def test_the_quality_report_flags_weak_records_time_gaps_and_overdue_plans() -> None:
    press = next(s["id"] for s in FX.rows("sources.jsonl") if s["type"] == "press_release")
    generated, product = "prd_w000000001", "prd_0000000005"
    reach = next(c for c in FX.rows("claims.jsonl") if c["subject"] == product and c["spec_key"] == "fixture_reach")
    first = {**reach, "valid_from": {"value": "2020", "precision": "year"},
             "valid_to": {"value": "2021", "precision": "year"}}
    later = {**reach, "id": "clm_00000000zz", "rank": 2, "valid_from": {"value": "2023", "precision": "year"}}
    planned = {"id": "evt_00000000zz", "version": 1, "product": product, "type": "eol_notice", "state": "planned",
               "date": {"value": "2026-01", "precision": "month"}, "source_refs": reach["source_refs"]}
    weak = lambda r: r["id"].startswith("clm_") and r["subject"] == generated
    coreless = lambda r: r["id"].startswith("clm_") and r["subject"] == "prd_w000000002" and r["spec_key"] in (
        "fixture_reach", "fixture_finish")
    records = [first if r["id"] == reach["id"] else {**r, "source_refs": [press]} if weak(r) else r
               for r in FX.records if not coreless(r)]
    found = {r["id"]: r for r in FX.json(FX.holding([*records, later, planned]), "quality", "report")["records"]}
    assert (found[generated]["weak"], found["prd_w000000002"]["weak"]) == (
        ["0 of 3 claims rest on a vendor document"], ["no core spec"])
    assert (found[product]["valid_time_gaps"], found[product]["overdue_events"]) == (["fixture_reach"],
                                                                                      ["evt_00000000zz"])
    assert (found["prd_0000000001"]["undated_sources"], found["prd_0000000003"]["vendor_backed"],
            found["prd_0000000004"]["missing_required"]) == (["src_0000000001"], 2, ["fixture_finish"])

def test_the_hubs_answer_in_their_shape(place: tuple[str, str]) -> None:
    hubs = FX.json(place, "category", "list")
    assert {h["id"] for h in hubs} == {c["id"] for c in INDEX["categories"] if c["products"]}
    shown = FX.json(place, "category", "show", hubs[0]["id"])
    assert shown["products"] == len(shown["cards"])
    used = next(v for v in VIEWS if v.get("hub"))
    assert FX.json(place, "hub", "show", used["hub"]["path"], used["slug"])["users"] == used["hub"]["users"]

def test_every_admin_read_has_its_command(place: tuple[str, str]) -> None:
    product = FX.rows("products.jsonl")[0]
    assert json.loads(FX.json(place, "record", "get", product["id"])["record"])["id"] == product["id"]
    missing = stores.cli(FX, place, "record", "get", "prd_zzzzzzzzzz", check=False)
    assert missing.returncode == 1 and "no record with id prd_zzzzzzzzzz" in missing.stderr
    assert {e["id"] for e in FX.json(place, "model", "show")["entities"]} >= {"Product", "Organization", "Claim"}
    assert FX.json(place, "index", "settings")["search"]["rrf_k"] == FX.model.registry.search.rrf_k
