from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from radar.build.llms import write_llms
from radar.tests.store import stores

FX = stores.fixture()
PROFILES = {p.category_id: p for p in FX.registry.profiles}
INTERNAL_IDS = re.compile(r"\b(?:" + "|".join(e.prefix for e in FX.schema.entities if e.internal) + r")_[0-9a-z]{10}\b")
INTERNAL_KEYS = {e.collection for e in FX.schema.entities if e.internal}
ORIGIN = "https://example.com"

@pytest.fixture(scope="module")
def llms(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("llms")
    write_llms(FX.read, out, FX.registry.default_language.code, ORIGIN)
    return out

def test_rows_are_the_profile_sections_in_order() -> None:
    assert FX.views
    for v in FX.views:
        sections = PROFILES[v["category"]].sections
        assert [c["key"] for c in v["core"]] == list(sections.core), v["slug"]
        assert [c["key"] for c in v["detail"]] == list(sections.detail), v["slug"]
        for row in v["versions"]:
            assert set(row) - {"id", "source"} <= set(sections.versions), v["slug"]
        for row in v["offerings"]:
            assert set(row) - {"id", "source"} <= set(sections.offerings), v["slug"]

def test_every_value_has_one_current_source_and_the_view_lists_only_those() -> None:
    by_id = {v["id"]: v for v in FX.views}
    for v in FX.views:
        listed = {s["id"] for s in v["sources"]}
        cells = [*v["core"], *v["detail"]]
        for m in v["models"]:
            own = {c["key"]: c.get("value") for c in by_id[m["id"]]["core"]}
            assert [c.get("value") for c in m["specs"]] == [own.get(c["key"]) for c in m["specs"]], m["id"]
        for c in cells:
            assert ("value" in c) == ("source" in c), (v["slug"], c["key"])
        cited = {c["source"] for c in cells if "source" in c}
        cited |= {r["source"] for k in ("versions", "offerings", "lifecycle") for r in v[k] if "source" in r}
        cited |= {v["status"]["source"]} if "source" in v.get("status", {}) else set()
        assert cited == listed, v["slug"]

def _view(name: str) -> dict:
    return next(v for v in FX.views if v["slug"] == f"example-devices__{name}")

def test_a_value_cites_the_preferred_source_type_then_the_newest() -> None:
    reach = next(c for c in _view("widget-two")["core"] if c["key"] == "fixture_reach")
    assert reach["source"] == "src_0000000001", "the datasheet, not the newer website page"
    finish = next(c for c in _view("widget-one-s")["core"] if c["key"] == "fixture_finish")
    assert finish["source"] == "src_0000000003", "the newer of two press releases"

def test_the_status_is_the_newest_event_else_the_observed_one() -> None:
    assert [(_view(n).get("status", {}).get("term", {}).get("id"), _view(n).get("status", {}).get("source"))
            for n in ("widget-three", "widget-one-s", "widget-one")] == [
        ("released", "src_0000000001"), ("active", "src_0000000001"), (None, None)]

def test_versions_follow_their_scheme() -> None:
    assert [r["label"] for r in _view("widget-two")["versions"]] == ["1.2.0", "1.10.0", "2.0.0"]
    assert [r["label"] for r in _view("widget-three")["versions"]] == ["C.02", "A.11", "B.07"]

def _cell(name: str, key: str) -> dict:
    return next(c for c in (*_view(name)["core"], *_view(name)["detail"]) if c["key"] == key).get("value", {})

def test_each_datatype_publishes_as_its_typed_value() -> None:
    assert _cell("widget-one-s", "fixture_reach") == {"quantity": {"value": 180.3, "unit": "mm"}}
    assert _cell("widget-one", "fixture_reach") == {"range": {"min": 180.0, "max": 250.0, "unit": "mm"}}
    assert _cell("widget-two", "fixture_label") == {"string": "Sealed housing"}
    assert [t["id"] for t in _cell("widget-two", "fixture_adapters")["terms"]] == ["socket_b", "socket_a"]
    assert _cell("widget-one-l", "fixture_mass")["none"]["label"]["en"] == "Not applicable"

def test_the_market_counts_what_the_fixture_states() -> None:
    view = json.loads((FX.public / "market.json").read_text(encoding="utf-8"))
    assert {"categories": [(c["category"], c["products"], c["vendors"]) for c in view["categories"]],
            "vendors": [(v["organization"]["slug"], v["products"], v["categories"]) for v in view["vendors"]],
            "countries": [(c["country"], c["organizations"], c["products"]) for c in view["countries"]],
            "consolidation": [(e.get("year"), e["organization"]["slug"], e["owner"]["slug"])
                              for e in view["consolidation"]],
            "organizations": view["organizations"]} == {
        "categories": [("fixture_domain.widgets", 21, 1)], "vendors": [("example-devices", 21, 1)],
        "countries": [("DE", 4, 21), ("US", 1, 0)],
        "consolidation": [(2021, "nordwerk-optics", "caldera-group"), (2016, "example-devices", "nordwerk-optics"),
                          (None, "halvard-optik", "caldera-group")],
        "organizations": 5}
    assert len(json.dumps(view)) < 100 * 1024

def test_spread_values_appear_only_on_family_pages() -> None:
    for v in FX.views:
        if v["kind"] != "family":
            assert not any(c.get("family_range") for c in (*v["core"], *v["detail"])), v["slug"]

def test_every_quantity_value_is_in_its_spec_unit() -> None:
    defs = FX.index["spec_definitions"]
    quantities = [(v["slug"], c["key"], c["value"]["quantity"]) for v in FX.views for c in (*v["core"], *v["detail"])
                  if "quantity" in c.get("value", {})]
    assert [(slug, key, q.get("unit")) for slug, key, q in quantities if q.get("unit") != defs[key].get("unit")] == []
    symbols = {u["symbol"]
               for u in json.loads((FX.out / "registry" / "units.json").read_text(encoding="utf-8"))}
    assert {d["unit"] for d in defs.values() if "unit" in d} <= symbols

def _keys(node: object) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in _keys(v)}
    return {k for v in node for k in _keys(v)} if isinstance(node, list) else set()

def test_nothing_internal_is_published(llms: Path) -> None:
    assert INTERNAL_KEYS and any((FX.out / "data" / f"{c}.jsonl").exists() for c in INTERNAL_KEYS), (
        "the fixture holds internal records")
    views = sorted(FX.public.rglob("*.json"))
    assert [(f.name, m) for f in (*views, llms / "llms.txt", llms / "llms-full.txt")
            for m in INTERNAL_IDS.findall(f.read_text(encoding="utf-8"))] == []
    leaked = {f.name: _keys(json.loads(f.read_text(encoding="utf-8"))) & INTERNAL_KEYS for f in views}
    assert {f: k for f, k in leaked.items() if k} == {}

def test_llms_full_txt_one_section_per_product(llms: Path) -> None:
    txt = (llms / "llms-full.txt").read_text(encoding="utf-8")
    products = FX.read.index().products
    assert products and txt.count("\n## ") == len(products)
    for p in products:
        assert f"- ID: `{p.id}`" in txt, f"missing section: {p.id}"
    for field in ("- Vendor:", "- Category:", "- Key specs:"):
        assert field in txt
    assert not any(line.lower().startswith(("generated:", "exported:")) for line in txt.splitlines())

def test_llms_txt_states_the_counts_and_domains(llms: Path) -> None:
    index = FX.read.index()
    counts = f"{len(index.products)} products from {len(index.organizations)} organizations"
    text = (llms / "llms.txt").read_text(encoding="utf-8")
    assert counts in text
    assert counts.replace("products", "machine-vision products") in (llms / "llms-full.txt").read_text(encoding="utf-8")
    labels = {d.id: d.label["en"] for d in index.domains}
    domains = list(dict.fromkeys(labels[c.domain] for c in index.categories))
    assert f"in {len(domains)} domains: {', '.join(domains)}." in text
    assert f"{ORIGIN}/llms-full.txt" in text and "<deploy-url>" not in text
    assert f"- Licence: {ORIGIN}/terms" in text
