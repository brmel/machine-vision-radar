from __future__ import annotations

import copy
import dataclasses
from datetime import date
from typing import Any, Callable

import pytest

from radar.adapters.files.json_parser import parse_catalog
from radar.domain.validation.context import Part, ValidationContext, Whole
from radar.domain.validation.rules.catalog import (category_and_roles, countries, entity_ids, references, variant_axes,
                                                   versions)
from radar.domain.validation.rules.claims import claim_profile, claim_values, dates, lifecycle
from radar.domain.validation.rules import changes, feed, unique
from radar.domain.validation.rules.registry import no_filler_text, vocabularies
from radar.domain.validation.rules.sources import source_integrity, source_preference
from radar.domain.model.registry import composed
from radar.domain.validation.runner import RULES, check
from radar.tests.fixtures.corpus import CORPUS, MODEL, REGISTRY, SCHEMA

TODAY = date(2026, 10, 17)

SPECS = sorted(REGISTRY.spec_definitions.values(), key=lambda s: s.id)
QUANTITY, TERM, STRING = (next(s.id for s in SPECS if s.datatype == d) for d in ("quantity", "term", "string"))
_PROFILED = next(p for p in REGISTRY.profiles if p.category_id == CORPUS["products"][0]["category"]).sections
OUTSIDE = next(s.id for s in SPECS if s.datatype == "quantity" and s.dimension == "length"
               and s.id not in {*_PROFILED.core, *_PROFILED.detail})

def _ctx(raw: dict[str, Any], registry=REGISTRY) -> ValidationContext:
    return ValidationContext(parse_catalog(raw, MODEL), registry, SCHEMA, TODAY, Part())

def _claim(raw: dict, n: int) -> dict:
    return next(c for c in raw["claims"] if c["id"] == f"clm_{n:010d}")

def _set(path: Callable[[dict], dict], key: str, value: Any) -> Callable[[dict], None]:
    return lambda raw: path(raw).__setitem__(key, value)

IMAGE = {"id": "doc_0000000002", "version": 1, "kind": "image", "mime": "image/png", "bytes": 1024,
         "sha256": "1" * 64, "subjects": ["prd_0000000001"], "rights": "vendor", "fetched_at": "2026-09-01T09:00:00Z"}

def _thumbnail(doc_id: str, *documents: dict) -> Callable[[dict], None]:
    return lambda raw: (raw["documents"].extend(documents), raw["products"][0].update(thumbnail=doc_id))

BREAKS: dict[str, tuple[Any, Callable[[dict], None]]] = {
    "prefix": (entity_ids, _set(lambda r: r["names"][0], "id", "org_0000000009")),
    "duplicate": (entity_ids, _set(lambda r: r["names"][1], "id", "nam_0000000001")),
    "gtin_check_digit": (entity_ids,
                         lambda r: r["identifiers"].append({**r["identifiers"][0], "id": "idn_0000000009",
                                                            "scheme": "gtin", "value": "4006381333932"})),
    "lei_length": (entity_ids,
                   lambda r: r["identifiers"].append({"id": "idn_0000000009", "version": 1, "subject": "org_0000000001",
                                                      "scheme": "lei", "value": "529900T8BM49AURSDO5"})),
    "scheme_wrong_subject": (entity_ids,
                             lambda r: r["identifiers"].append({**r["identifiers"][0], "id": "idn_0000000009",
                                                                "scheme": "lei", "value": "529900T8BM49AURSDO55"})),
    "qualifier_not_a_spec": (claim_values,
                             _set(lambda r: r["relations"][0], "qualifiers", {"not_a_spec": {"boolean": True}})),
    "qualifier_wrong_datatype": (claim_values,
                                 _set(lambda r: r["relations"][0], "qualifiers", {QUANTITY: {"boolean": True}})),
    "dangling": (references, _set(lambda r: _claim(r, 1), "subject", "prd_0000000099")),
    "wrong_kind": (references, _set(lambda r: _claim(r, 1), "source_refs", ["doc_0000000001"])),
    "unknown_term": (vocabularies, _set(lambda r: r["observed_statuses"][0], "status", "not_a_status")),
    "slug_without_maker": (category_and_roles, _set(lambda r: r["products"][0], "slug", "no-maker-prefix")),
    "role_twice": (category_and_roles,
                   lambda r: r["product_org_roles"].append({**r["product_org_roles"][0], "id": "por_0000000099"})),
    "unknown_category": (vocabularies,
                         _set(lambda r: next(p for p in r["products"] if p["id"] == _claim(r, 1)["subject"]),
                              "category", "not_a_category")),
    "unknown_axis": (vocabularies, _set(lambda r: r["products"][2], "variant_axes", {"flavour": "color"})),
    "wrong_dimension": (claim_values, _set(lambda r: _claim(r, 1)["value"]["quantity"], "unit", "mm")),
    "wrong_variant": (claim_values, _set(lambda r: _claim(r, 5), "value", {"string": "global"})),
    "term_outside_vocab": (claim_values, _set(lambda r: _claim(r, 6)["value"], "terms", ["roi", "laser"])),
    "range_backwards": (claim_values, _set(lambda r: _claim(r, 4)["value"]["range"], "min", 90)),
    "outside_bounds": (claim_values, _set(lambda r: _claim(r, 1)["value"]["quantity"], "value", 1e15)),
    "terms_repeat": (claim_values, _set(lambda r: _claim(r, 6)["value"], "terms", ["roi", "roi"])),
    "none_on_term_set": (claim_values, _set(lambda r: _claim(r, 6), "value", {"none": "not_applicable"})),
    "unknown_reason": (vocabularies, _set(lambda r: _claim(r, 1), "value", {"none": "no_such_reason"})),
    "two_first_values": (claim_values,
                         lambda r: r["claims"].append({**_claim(r, 11), "id": "clm_0000000097",
                                                       "value": {"quantity": {"value": 72, "unit": "db"}}})),
    "claim_outside_profile": (claim_profile, lambda r: r["claims"].append({**_claim(r, 1), "id": "clm_0000000098",
        "spec_key": OUTSIDE, "value": {"quantity": {"value": 16, "unit": "mm"}}})),
    "marketing_filler": (no_filler_text,
                         _set(lambda r: r["organizations"][0], "summary", {"en": "Industry-leading cameras."})),
    "future_date": (dates, _set(lambda r: r["sources"][0], "published_at", {"value": "2027", "precision": "year"})),
    "future_instant": (dates, _set(lambda r: r["sources"][0], "retrieved_at", "2026-12-01T00:00:00Z")),
    "bad_precision": (dates,
                      _set(lambda r: r["sources"][0], "published_at", {"value": "2025-Q5", "precision": "quarter"})),
    "future_actual_event": (dates, _set(lambda r: r["lifecycle_events"][1], "state", "actual")),
    "duplicate_identifier": (entity_ids,
                             lambda r: r["identifiers"].append({**r["identifiers"][0], "id": "idn_0000000002"})),
    "duplicate_product_slug": (unique, _set(lambda r: r["products"][1], "slug", "vexa-optics__vx")),
    "duplicate_organization_slug": (unique, _set(lambda r: r["organizations"][1], "slug", "vexa-optics")),
    "one_file_twice": (unique, lambda r: r["documents"].append({**r["documents"][0], "id": "doc_0000000009"})),
    "country_unassigned": (countries, _set(lambda r: r["organizations"][0], "country", "XX")),
    "planned_without_announcement": (dates,
                                     _set(lambda r: r["lifecycle_events"][1], "source_refs", ["src_0000000002"])),
    "unknown_label": (versions, _set(lambda r: _claim(r, 11)["applies_to_versions"], "min", "9.0.0")),
    "range_on_other_product": (versions,
                               _set(lambda r: _claim(r, 11)["applies_to_versions"], "product", "prd_0000000001")),
    "mixed_schemes": (versions, _set(lambda r: r["product_versions"][0], "scheme", "calver")),
    "variant_diverges": (variant_axes, lambda r: r["claims"].append(
        {**_claim(r, 3), "id": "clm_0000000099", "subject": "prd_0000000003"} | {
            "value": {"quantity": {"value": 2.2, "unit": "um"}}})),
    "inherited_on_top": (source_preference, lambda r: (_claim(r, 10).update(rank=1), _claim(r, 4).update(rank=2))),
    "filler": (no_filler_text, _set(lambda r: r["names"][1], "value", "N/A")),
    "revised_without_reviser": (lifecycle, lambda r: r["lifecycle_events"][3].pop("revised_by")),
    "successor_without_relation": (lifecycle, lambda r: r["relations"].pop()),
    "successor_on_other_event": (lifecycle, _set(lambda r: r["lifecycle_events"][0], "successor", "prd_0000000004")),
    "version_gap": (changes, lambda r: (r["changes"][3].update(version=4), r["products"][3].update(version=4))),
    "changes_without_entity": (changes, lambda r: r["alt_names"].pop(0)),
    "stored_version_behind": (changes, _set(lambda r: r["products"][3], "version", 2)),
    "replay_differs": (changes, _set(lambda r: r["products"][3], "website_url", "https://elsewhere.example.com")),
    "patch_does_not_apply": (changes,
                             _set(lambda r: r["changes"][2], "patch",
                                  [{"op": "replace", "path": "website_url", "value": "\"https://vexa.example.com\""}])),
    "unsourced_fact": (changes,
                       _set(lambda r: r["changes"][0], "patch", [{"op": "add", "path": "text", "value": "\"x\""}])),
    "proposal_shape": (changes, _set(lambda r: r["changes"][1], "proposal", "my-proposal")),
    "no_source_url": (source_integrity, lambda r: (r["sources"][0].update(url=""), r["sources"][0].pop("document"))),
    "source_url_twice": (unique, lambda r: r["sources"].append({**r["sources"][1], "id": "src_0000000009"})),
    "feed_uncited": (feed, lambda r: r["feed_items"][0]["body"][0].update(cites=["prd_0000000001"])),
    "feed_undated_source": (feed, lambda r: r["feed_items"][0].pop("event_source")),
    "feed_personal_byline": (feed,
                             _set(lambda r: r["feed_items"][0], "byline", {"en": "A. Person", "fr": "A. Person"})),
    "feed_spaced_slug": (feed, _set(lambda r: r["feed_items"][0], "slug", "VX 500 joins")),
    "thumbnail_missing": (references, _thumbnail("doc_9999999999")),
    "thumbnail_not_an_image": (references, _thumbnail("doc_0000000001")),
    "thumbnail_not_public": (references, _thumbnail(IMAGE["id"], IMAGE)),
    "thumbnail_of_another_product": (references,
                                     _thumbnail(IMAGE["id"],
                                                {**IMAGE, "rights": "own", "subjects": ["prd_0000000002"]})),
    "release_notes_without_version": (references,
                                      lambda r: r["documents"].append(
                                          {**IMAGE, "kind": "release_notes", "mime": "application/pdf"})),
}

def _errors(ctx: ValidationContext, rules=RULES) -> list[str]:
    return [f"{f.rule}: {f.entity_id}: {f.message}" for f in check(ctx, rules).errors]

def test_corpus_passes_every_rule() -> None:
    assert _errors(_ctx(CORPUS)) == []

def test_a_slug_without_its_maker_part_names_the_makers_slug() -> None:
    raw = copy.deepcopy(CORPUS)
    raw["products"][0]["slug"] = "vx"
    assert [e for e in _errors(_ctx(raw)) if e.startswith(category_and_roles.NAME)] == [
        f"{category_and_roles.NAME}: prd_0000000001: slug 'vx' is not '<maker>__<product>', the maker part from its "
        "maker's slug: vexa-optics"]

def test_a_change_may_restate_a_url_that_reads_like_filler() -> None:
    raw = copy.deepcopy(CORPUS)
    raw["changes"][0]["patch"].append({"op": "add", "path": "url",
                                       "value": '"https://example.com/news/cutting-edge-widgets"'})
    assert [e for e in _errors(_ctx(raw)) if e.startswith("no_filler_text")] == []

def test_filler_is_what_the_registry_lists() -> None:
    raw = copy.deepcopy(CORPUS)
    BREAKS["marketing_filler"][1](raw)
    unlisted = dataclasses.replace(REGISTRY, filler=dataclasses.replace(REGISTRY.filler, anywhere=()))
    assert [e for e in _errors(_ctx(raw, unlisted)) if e.startswith("no_filler_text")] == []

def test_a_retracted_entity_needs_no_stored_record() -> None:
    raw = copy.deepcopy(CORPUS)
    note = raw["alt_names"].pop(0)
    raw["changes"].append({**raw["changes"][0], "id": "chg_0000000009", "version": 2,
                           "recorded_at": "2026-09-03T08:00:00Z",
                           "patch": [{"op": "remove", "path": k} for k in note if k != "version"]})
    assert _errors(_ctx(raw)) == []

@pytest.mark.parametrize("name", sorted(BREAKS))
def test_rule_fails_and_passes_when_removed(name: str) -> None:
    rule, brk = BREAKS[name]
    raw = copy.deepcopy(CORPUS)
    brk(raw)
    ctx = _ctx(raw)
    errors = _errors(ctx)
    assert errors and all(e.startswith(f"{rule.NAME}:") for e in errors), errors
    assert _errors(ctx, [r for r in RULES if r is not rule.check]) == []

def test_one_url_is_one_source_its_new_version_included_in_a_part_or_the_whole() -> None:
    raw = copy.deepcopy(CORPUS)
    held = raw["sources"][1]
    raw["sources"][1] = {**held, "version": 2, "retrieved_at": "2026-10-01T09:00:00Z"}
    assert _errors(_ctx(raw), [unique.check]) == []
    raw["sources"].append({**held, "id": "src_0000000009"})
    ctx = _ctx(raw)
    pair = [f"unique: {held['id']}: Source.url '{held['url']}' is also held by src_0000000009",
            f"unique: src_0000000009: Source.url '{held['url']}' is also held by {held['id']}"]
    assert _errors(ctx, [unique.check]) == _errors(dataclasses.replace(ctx, scope=Whole()), [unique.check]) == pair

def test_a_change_that_replaces_a_permanent_field_is_refused() -> None:
    raw = copy.deepcopy(CORPUS)
    product = next(p for p in raw["products"] if p["id"] == "prd_0000000004")
    product.update(slug=f"{product['slug']}-renamed", version=4)
    raw["changes"].append({**raw["changes"][3], "id": "chg_0000000005", "version": 4, "patch": [
        {"op": "replace", "path": "slug", "value": f'"{product["slug"]}"'}]})
    assert _errors(_ctx(raw)) == [f"permanent: prd_0000000004: Product.slug never changes once set; version 4 sets it "
                                  f'to "{product["slug"]}"']

def test_planned_event_past_its_date_is_flagged() -> None:
    raw = copy.deepcopy(CORPUS)
    raw["lifecycle_events"][1]["date"] = {"value": "2026-01", "precision": "month"}
    res = check(_ctx(raw), [dates.check])
    assert res.ok and any("has passed" in w.message for w in res.warnings)

def test_a_product_takes_a_spec_group_beyond_its_profile() -> None:
    raw = copy.deepcopy(CORPUS)
    product = next(p for p in raw["products"] if p["id"] == _claim(raw, 1)["subject"])
    profile = next(p for p in REGISTRY.profiles if p.category_id == product["category"])
    group, spec = next((g, REGISTRY.spec_definitions[k]) for g in REGISTRY.spec_groups.values()
                       if g.id not in profile.groups for k in g.specs
                       if REGISTRY.spec_definitions[k].dimension == "length")
    raw["claims"].append({**_claim(raw, 1), "id": "clm_0000000096", "spec_key": spec.id,
                          "value": {"quantity": {"value": 16, "unit": "mm"}}})
    assert _errors(_ctx(raw), (claim_profile.check,))
    product["spec_groups"] = [group.id]
    assert _errors(_ctx(raw), (claim_profile.check,)) == []

def test_a_profile_takes_no_spec_twice() -> None:
    taken = next(p for p in REGISTRY.profiles if p.groups)
    with pytest.raises(ValueError, match="in two groups"):
        composed(taken, REGISTRY.spec_groups)
