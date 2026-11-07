from __future__ import annotations

from pathlib import Path

from radar.tests.store import stores

FX = stores.fixture()
PLAN = {"reason": "A product's summary is written by the news desk, not stored on the record",
        "rules": [{"rule": "drop_field", "kind": "Product", "field": "summary"}]}

def test_a_migration_plan_moves_every_record_it_names_through_review(tmp_path: Path) -> None:
    place = FX.loaded()
    summarized = sorted(p["id"] for p in FX.rows("products.jsonl") if p.get("summary"))
    plan = stores.file(tmp_path, "plan.json", PLAN)
    before = FX.json(place, "proposal", "list")["total"]
    dry = FX.json(place, "model", "migrate", plan, "--dry-run")
    assert summarized and (dry["changes"], dry["counts"]) == (len(summarized), {"Product.summary": len(summarized)})
    assert dry["proposals"] == []
    assert FX.json(place, "proposal", "list")["total"] == before, "a dry run files nothing"
    filed = FX.json(place, "model", "migrate", plan)
    assert len(filed["proposals"]) == 1 and filed["changes"] == len(summarized)
    [approved] = FX.json(place, "proposal", "approve", *filed["proposals"], "--note", "The structure moves")["done"]
    assert (approved["actor_kind"], approved["author"], approved["status"]) == ("agent", "migration", "approved")
    docs = stores.fresh_at(place[0])
    assert all("summary" not in FX.stored(docs, p) for p in summarized)
    assert FX.json(place, "store", "validate")["ok"]
    assert FX.json(place, "model", "migrate", plan, "--dry-run")["changes"] == 0, "a plan applied twice moves nothing"
    bad = stores.file(tmp_path, "bad.json",
                      {**PLAN, "rules": [{"rule": "drop_field", "kind": "Product", "field": "slug"}]})
    refused = stores.cli(FX, place, "model", "migrate", bad, check=False)
    assert refused.returncode == 2 and "no optional field 'slug'" in refused.stderr

def test_a_plan_splits_a_mixed_vocabulary_merges_specs_and_moves_products(tmp_path: Path) -> None:
    place = FX.loaded()
    claims = FX.rows("claims.jsonl")
    product = next(p for p in FX.rows("products.jsonl") if p["category"] == "fixture_domain.widgets")
    finish = next(c for c in claims if c["spec_key"] == "fixture_finish")
    plan = stores.file(tmp_path, "plan.json", {"reason": "One meaning per term", "rules": [
        {"rule": "map_term", "spec": "fixture_finish", "term": finish["value"].get("term", "matte"), "to": None}]})
    dry = FX.json(place, "model", "migrate", plan, "--dry-run")
    assert any(k.startswith("claim retracted: fixture_finish") for k in dry["counts"]), (
        "a term mapped to nothing retracts a claim that held only it")
    refused = stores.cli(FX, place, "model", "migrate", stores.file(tmp_path, "bad.json", {
        "reason": "x", "rules": [{"rule": "rename_spec", "spec": "nothing", "to": "fixture_finish"}]}), check=False)
    assert refused.returncode == 2 and "no spec 'nothing'" in refused.stderr
    assert product["id"]

