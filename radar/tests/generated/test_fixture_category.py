from __future__ import annotations

import json
from pathlib import Path

import pytest

from radar import paths
from radar.tests.fixtures.fixture_category import FIXTURE, build

REGISTRY = FIXTURE["registry"]
REGISTRY_RIGHTS = json.loads(
    (paths.REGISTRY / "vocabularies" / "media_rights.json").read_text(encoding="utf-8"))
DATA = FIXTURE["data"]
[CATEGORY] = REGISTRY["categories.json"]
[DOMAIN] = REGISTRY["vocabularies/domains.json"]
[STAGE] = REGISTRY["vocabularies/pipeline_stages.json"]
SPECS = REGISTRY["spec_definitions.json"]
PROFILE = REGISTRY[next(k for k in REGISTRY if k.startswith("category_profiles/"))]
NAMES = {n["subject"]: n["value"] for n in DATA["names.jsonl"] if n["is_primary"]}
FAMILY = next(p for p in DATA["products.jsonl"] if any(m.get("parent") == p["id"] for m in DATA["products.jsonl"]))
MODELS = [p for p in DATA["products.jsonl"] if p.get("parent") == FAMILY["id"]]
VERSIONED = next(p for p in DATA["products.jsonl"] if p["version"] > 1)

@pytest.fixture(scope="module")
def out(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("fixture-category")
    build(out)
    return out

def _read(out: Path, *parts: str) -> dict:
    return json.loads((out / "dist" / "public").joinpath(*parts).read_text(encoding="utf-8"))

def test_the_index_carries_the_new_category_domain_and_stage(out: Path) -> None:
    index = _read(out, "index.json")
    category = next(c for c in index["categories"] if c["id"] == CATEGORY["id"])
    assert (category["domain"], category["pipeline"], category["glyph"]) == (
        DOMAIN["id"], [STAGE["id"]], CATEGORY["glyph"])
    assert DOMAIN in index["domains"] and index["pipeline_stages"][-1] == STAGE
    groups = {g["id"]: g for g in REGISTRY["spec_groups.json"]}
    assert category["core"] == PROFILE["sections"]["core"]
    assert all(index["spec_groups"][g] == groups[g]["label"] for g in PROFILE["groups"])
    assert category["products"] == len(DATA["products.jsonl"])
    for spec in SPECS:
        assert index["spec_definitions"][spec["id"]]["label"] == spec["label"]

def test_the_listing_page_counts_its_facets(out: Path) -> None:
    page = _read(out, "categories", CATEGORY["id"], "1.json")
    assert {p["id"] for p in page["products"]} == {p["id"] for p in DATA["products.jsonl"]}
    enums = [f for f in page["facets"] if f["kind"] == "enum"]
    assert len(enums) == len([f for f in PROFILE["facets"]
                              if next(s for s in SPECS if s["id"] == f["field"])["datatype"] == "term"])
    for enum in enums:
        terms = [c["value"]["term"] for c in DATA["claims.jsonl"] if c["spec_key"] == enum["spec_key"]
                 and "term" in c["value"]]
        assert {o["id"]: o["count"] for o in enum["options"]} == {t: terms.count(t) for t in set(terms)}
    published = {f["spec_key"]: len({c["subject"] for c in DATA["claims.jsonl"] if c["spec_key"] == f["spec_key"]
                                     and "none" not in c["value"]}) for f in page["facets"]}
    assert [f["count"] for f in page["facets"]] == [published[f["spec_key"]] for f in page["facets"]] == sorted(
        published.values(), reverse=True)

def test_family_models_media_and_history_follow(out: Path) -> None:
    family = _read(out, "products", f"{FAMILY['id']}.json")
    assert [m["name"] for m in family["models"]] == sorted(NAMES[m["id"]] for m in MODELS)
    model = _read(out, "products", f"{MODELS[0]['id']}.json")
    assert model["family"]["id"] == FAMILY["id"]
    family_docs = [d for d in DATA["documents.jsonl"] if FAMILY["id"] in d["subjects"]]
    assert [m["kind"]["id"] for m in family["media"]] == [d["kind"] for d in family_docs]
    public = {r["id"] for r in REGISTRY_RIGHTS if r.get("public")}
    for m, d in zip(family["media"], family_docs):
        assert (m["href"].startswith("https://firebasestorage.googleapis.com/") if d["rights"] in public
                else m["href"] == d["source_url"])
    versioned = _read(out, "products", f"{VERSIONED['id']}.json")
    assert [m["kind"]["id"] for m in versioned["media"]] == ["manual", "release_notes"]
    assert versioned["media"][1]["version"] == "1.2.0"
    assert versioned["media"][1]["source_url"] == "https://example.com/widgets/two/releases/1.2.0.txt"
    assert versioned["media"][1]["href"].startswith("https://firebasestorage.googleapis.com/")
    history = _read(out, "history", f"{VERSIONED['id']}.json")
    assert [(v["entity"], v["version"], v.get("spec")) for v in history["versions"]] == [
        (VERSIONED["id"], 3, None), ("clm_0000000014", 2, "fixture_colour"), (VERSIONED["id"], 2, None),
        (VERSIONED["id"], 1, None), ("clm_0000000014", 1, "fixture_colour")]

def test_identifiers_and_relations_read_from_each_side(out: Path) -> None:
    rows = {pid: _read(out, "products", f"{pid}.json")
            for pid in ("prd_0000000003", "prd_0000000004", "prd_0000000005")}
    assert [(i["scheme"]["id"], i.get("schema_org")) for i in rows["prd_0000000003"]["identifiers"]] == [
        ("part_number", "mpn"), ("gtin", "gtin")]
    assert rows["prd_0000000003"]["vendor"]["id"] == "org_0000000001"
    assert [(r["type"], r["label"]["en"], r["product"]["id"], r["basis"], r.get("schema_org"))
            for r in rows["prd_0000000004"]["relations"]] == [
("accessory_for", "Accessory for", "prd_0000000005", "asserted", "isAccessoryOrSparePartFor"),
("rebrand_of", "Sold as", "prd_0000000003", "derived", None)]
    assert [(r["label"]["en"], r["product"]["id"]) for r in rows["prd_0000000005"]["relations"]] == [
        ("Accessories", "prd_0000000004"), ("Replaces", "prd_0000000002")]
