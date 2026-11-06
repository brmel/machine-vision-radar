from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

from radar.paths import DEV
from radar.adapters.files.json_parser import parse_catalog
from radar.domain.model.entities import ClaimValueQuantity, VersionRange
from radar.tests.fixtures.corpus import CORPUS, FIXTURE, MODEL, REGISTRY

def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "radar", *args], cwd=DEV, capture_output=True, text=True)

PROBES: dict[str, tuple[Callable[[dict], None], str]] = {
    "typo_top_level_key": (lambda r: r.__setitem__("prodcuts", r.pop("products")),
                           "unknown top-level key(s) ['prodcuts']"),
    "missing_required_field": (lambda r: r["products"][0].pop("slug"), "missing required field 'slug' of Product"),
    "object_in_instant": (lambda r: r["claims"][0].__setitem__("recorded_at", {"at": "2026"}),
                          "recorded_at (Instant): expected string, got object"),
    "unknown_key_in_quantity": (lambda r: r["claims"][0]["value"]["quantity"].__setitem__("vaule", 1),
                                "unknown field(s) ['vaule'] for Quantity"),
    "partial_date_without_precision": (lambda r: r["organizations"][0]["founded"].pop("precision"),
                                       "missing required field 'precision' of PartialDate"),
    "localized_text_without_en": (lambda r: r["organizations"][0].__setitem__("summary", {"fr": "x"}),
                                  "LocalizedText requires key 'en'"),
    "enum_outside_values": (lambda r: r["changes"][0].__setitem__("actor_kind", "robot"), "expected one of"),
    "two_union_tags": (lambda r: r["claims"][0].__setitem__("value", {"term": "a", "string": "b"}), "exactly one of"),
    "null_optional": (lambda r: r["products"][0].__setitem__("summary", None), "got null"),
    "boolean_as_number": (lambda r: r["claims"][0]["value"]["quantity"].__setitem__("value", True),
                          "expected number, got boolean"),
    "bad_entity_id": (lambda r: r["products"][0].__setitem__("id", "prd_ABC"), "is not a valid EntityId"),
    "empty_source_refs": (lambda r: r["claims"][0].__setitem__("source_refs", []), "needs at least 1 item"),
    "unsourced_offering": (lambda r: r["offerings"][0].__setitem__("source_refs", []), "needs at least 1 item"),
    "unsourced_relation": (lambda r: r["relations"][0].__setitem__("source_refs", []), "needs at least 1 item"),
    "rank_below_one": (lambda r: r["claims"][0].__setitem__("rank", -5), "rank: must be at least 1, got -5"),
    "empty_localized_text": (lambda r: r["organizations"][0].__setitem__("summary", {"en": " "}),
                             "summary.en: LocalizedText text must not be empty"),
    "nan_number": (lambda r: r["claims"][0]["value"]["quantity"].__setitem__("value", float("nan")),
                   "non-finite number NaN is not allowed"),
    "wrong_id_prefix": (lambda r: r["names"][0].__setitem__("id", "org_0000000009"), "Name id must start with 'nam_'"),
}

@pytest.mark.parametrize("name", sorted(PROBES))
def test_probe_exits_1_with_message(name: str, tmp_path: Path) -> None:
    brk, expected = PROBES[name]
    raw = copy.deepcopy(CORPUS)
    brk(raw)
    path = tmp_path / "model.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    r = _cli("model", "validate", str(path))
    assert r.returncode == 1 and expected in r.stdout + r.stderr and "Traceback" not in r.stderr, r.stdout + r.stderr

def test_missing_and_invalid_files(tmp_path: Path) -> None:
    r = _cli("model", "validate", str(tmp_path / "absent.json"))
    assert r.returncode == 1 and "model file not found" in r.stderr
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    r = _cli("model", "validate", str(tmp_path / "bad.json"))
    assert r.returncode == 1 and "invalid JSON" in r.stderr

def test_only_a_catalog_folder_warns_on_its_empty_categories_and_products_missing_a_required_spec(
        tmp_path: Path) -> None:
    stated = {**CORPUS["claims"][0], "id": "clm_00000000zz", "spec_key": "interfaces", "value": {"terms": ["gige"]}}
    for collection, rows in {**CORPUS, "claims": [*CORPUS["claims"], stated]}.items():
        (tmp_path / f"{collection}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    folder, file, alone = (json.loads(_cli("model", "validate", *path, "--json").stdout)
                           for path in ([str(tmp_path)], [str(FIXTURE)], []))
    empty = set(REGISTRY.categories) - {p["category"] for p in CORPUS["products"]}
    missing = {p["id"]: f"states no interfaces, required in {p['category']}" for p in CORPUS["products"]
               if p["id"] != stated["subject"]}
    assert (folder["ok"] and file["ok"] and {w["entity_id"] for w in folder["warnings"]} == empty | missing.keys()
            and {w["entity_id"]: w["message"] for w in folder["warnings"] if w["rule"] == "claim_profile"} == missing
            and file["warnings"] == alone["warnings"] == [])

def _vrange(**kw: Any) -> VersionRange:
    return VersionRange(product="prd_0000000002", **kw)

def test_catalog_is_typed_and_orders_versions_by_scheme() -> None:
    cat = parse_catalog(CORPUS, MODEL)
    assert isinstance(cat.claims_for("prd_0000000002")[0].value, ClaimValueQuantity)
    assert [v.label for v in cat.versions_of("prd_0000000002")] == ["1.2.0", "1.10.0"]
    assert [v.label for v in cat.resolve(_vrange(min="1.10.0"))] == ["1.10.0"]
    assert [v.label for v in cat.resolve(_vrange(exclude=("1.2.0",)))] == ["1.10.0"]
    twice = parse_catalog({**CORPUS,
                           "product_versions": [*CORPUS["product_versions"],
                                                {**CORPUS["product_versions"][0], "id": "ver_0000000099"}]}, MODEL)
    assert len(twice.resolve(_vrange(min="1.2.0"))) == 3
    scoped = next(c["spec_key"] for c in CORPUS["claims"] if c.get("applies_to_versions"))
    assert scoped not in {c.spec_key for c in cat.claims_for("prd_0000000002")}

def test_unknown_version_scheme_is_refused() -> None:
    raw = copy.deepcopy(CORPUS)
    for v in raw["product_versions"]:
        v["scheme"] = "lunar"
    with pytest.raises(ValueError, match="no ordering for version scheme 'lunar'"):
        parse_catalog(raw, MODEL).versions_of("prd_0000000002")
