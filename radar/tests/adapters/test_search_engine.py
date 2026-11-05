import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from radar.tests.fixtures.fixture_category import FilesCatalogRepository
from radar.adapters.ai.search.engine import ShardedSearch
from radar.adapters.ai.search.fastembed_embedder import FastembedEmbedder
from radar.adapters.ai.search.files import CURRENT, BlobStoreIndexFiles
from radar.adapters.storage.blobs import StorageBlobStore
from radar.domain.model.entities import EvalQuery
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.adapters.web.api import FindEndpoint
from radar.domain.ports.search.search_engine import Hit, IndexMismatch, SearchRequest
from radar.domain.ports.web.endpoint import Request
from radar.domain.search.eval import evaluate
from radar.paths import DEV
from radar.tests.store import stores

FX = stores.fixture()
PUBLIC, MODEL, READ, REGISTRY = FX.public, FX.model, FX.read, FX.model.registry

EMBEDDER = REGISTRY.search.model
OTHER_MODEL = "BAAI/bge-small-en-v1.5"

def _engine(bucket: StorageBlobStore, model: str = EMBEDDER, read: CatalogRepository = READ) -> ShardedSearch:
    return ShardedSearch(BlobStoreIndexFiles(bucket), FastembedEmbedder(model), REGISTRY, read)

def _files(bucket: StorageBlobStore) -> dict[str, bytes]:
    return {name: b"".join(bucket.read(name)) for name, _ in bucket.sizes()}

def test_the_embedder_meets_its_contract() -> None:
    embedder = FastembedEmbedder(EMBEDDER)
    vectors = embedder.embed(["a glossy widget", "un widget brillant", "a glossy widget"])
    assert len(vectors) == 3 and embedder.embed([]) == []
    assert all(len(v) == embedder.model.dimension and abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-6 for v in vectors)
    assert vectors[0] == vectors[2] and embedder.model.model_id == EMBEDDER

def test_offline_a_model_not_in_the_cache_says_how_to_fetch_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", str(tmp_path))
    with pytest.raises(RuntimeError, match=f"FASTEMBED_CACHE_PATH={tmp_path} python3 -c"):
        FastembedEmbedder(EMBEDDER).embed(["a glossy widget"])

def test_onnx_runtime_telemetry_is_off_before_it_loads() -> None:
    probe = ("import os, sys\nfrom radar.adapters.ai.search.fastembed_embedder import FastembedEmbedder\n"
             "FastembedEmbedder(sys.argv[1]).model\nprint(os.environ.get('ORT_DISABLE_TELEMETRY'), 'onnxruntime' in "
             "sys.modules)")
    env = {k: v for k, v in os.environ.items() if k != "ORT_DISABLE_TELEMETRY"}
    done = subprocess.run([sys.executable, "-c", probe, EMBEDDER], capture_output=True, text=True, timeout=120, env=env,
                          cwd=DEV, check=True)
    assert done.stdout.split() == ["1", "True"]

def test_two_builds_of_the_same_read_model_are_byte_identical() -> None:
    a, b = stores.blobs(), stores.blobs()
    first, second = _engine(a).index("rebuild"), _engine(b).index("rebuild")
    assert first.version == second.version
    assert _files(a) == _files(b)

def test_the_manifest_names_the_model_and_fingerprints_every_product() -> None:
    bucket = stores.blobs()
    built_ = _engine(bucket).index("rebuild")
    files = _files(bucket)
    manifest = json.loads(files[json.loads(files[CURRENT])["manifest"]])
    cards = READ.index().products
    assert manifest["version"] == built_.version
    assert (manifest["embedder"]["model_id"], manifest["embedder"]["dimension"]) == (EMBEDDER, 384)
    assert set(manifest["products"]) == {c.id for c in cards} == set(built_.embedded)
    assert sum(s["count"] for s in manifest["shards"]) == len(cards)
    assert {s["category"] for s in manifest["shards"]} == {c.category for c in cards}

def test_an_update_embeds_only_the_changed_product_and_drops_the_removed_one(tmp_path: Path) -> None:
    public = Path(shutil.copytree(PUBLIC, tmp_path / "public"))
    bucket = stores.blobs()
    engine = _engine(bucket, read=FilesCatalogRepository(public, MODEL))
    engine.index("rebuild")
    assert engine.index("update").embedded == ()

    changed, removed = FilesCatalogRepository(public, MODEL).index().products[:2]
    view = json.loads((public / "products" / f"{changed.id}.json").read_text())
    (public / "products" / f"{changed.id}.json").write_text(
        json.dumps({**view, "summary": {"en": "A changed summary.", "fr": "Un résumé changé."}}))
    idx = json.loads((public / "index.json").read_text())
    (public / "index.json").write_text(json.dumps({**idx,
                                                   "products": [c for c in idx["products"] if c["id"] != removed.id]}))

    before = engine.files()
    update = engine.index("update")
    assert (update.embedded, update.removed) == ((changed.id,), (removed.id,))
    stored = {name for name, _ in bucket.sizes()}
    assert engine.files() <= stored and before - engine.files() and (stored - engine.files()) <= before

def test_another_model_means_a_full_index_and_a_query_with_it_fails_on_the_old_one() -> None:
    bucket = stores.blobs()
    _engine(bucket).index("rebuild")
    with pytest.raises(IndexMismatch, match=f"{OTHER_MODEL}.*index rebuild"):
        _engine(bucket, OTHER_MODEL).search(SearchRequest("widget", 5, semantic=True))
    with pytest.raises(IndexMismatch):
        _engine(bucket, OTHER_MODEL).search(SearchRequest("a shiny polished gadget", 5))
    assert _engine(bucket, OTHER_MODEL).search(SearchRequest("widget", 5))
    rebuilt = _engine(bucket, OTHER_MODEL).index("update")
    assert len(rebuilt.embedded) == rebuilt.products

def _find(engine: ShardedSearch, body: object, method: str = "POST") -> tuple[int, dict]:
    response = FindEndpoint(engine, lambda job: job).respond(
        Request(method, "/api/find", json.dumps(body).encode(), {}, "203.0.113.7"))
    return response.status, dict(response.body or {})

def test_find_ranks_by_words_then_by_meaning_and_answers_503_without_an_index() -> None:
    glossy = next(c for c in READ.index().products if c.summary and "glossy" in c.summary["en"])
    status, body = _find(FX.search_engine, {"words": glossy.name})
    assert (status, body["ranking"], body["products"][0]["id"]) == (200, "words", glossy.id)
    meant = _find(FX.search_engine, {"words": "a shiny polished gadget"})[1]
    assert meant["ranking"] == "meaning" and glossy.id in [p["id"] for p in meant["products"][:5]]
    assert _find(FX.search_engine, {"words": "zzqxv"})[1] == {"ranking": "words", "products": []}
    refused = [({}, "POST"), ({"words": " "}, "POST"), ({"words": "x" * 301}, "POST"), (["widget"], "POST"),
               ({"words": glossy.name}, "GET")]
    assert [_find(FX.search_engine, b, m)[0] for b, m in refused] == [400] * 5
    assert _find(_engine(stores.blobs()), {"words": glossy.name})[0] == 503

@pytest.mark.parametrize("semantic", [False, True])
def test_the_synthetic_queries_clear_their_floor(semantic: bool) -> None:
    engine = FX.search_engine
    queries = [EvalQuery(**{**q, "targets": tuple(q["targets"])}) for q in FX.rows("eval_queries.jsonl")]
    score = evaluate(queries, lambda q, k: engine.search(SearchRequest(q, k, semantic)))
    assert {q.language for q in queries} == {"en", "fr"}
    assert score.hit_rate >= 1.0, [o for o in score.outcomes if o.rank is None]

CONFIG = REGISTRY.search
ALIASES = [row for file in ("alt_names.jsonl", "names.jsonl") for row in FX.rows(file) if not row.get("is_primary")]

def _words(query: str, engine: ShardedSearch | None = None) -> list[Hit]:
    return (engine or FX.search_engine).search(SearchRequest(query, None))

def _summarised(tmp_path: Path, summaries: list[str]) -> tuple[ShardedSearch, list[str]]:
    public = Path(shutil.copytree(PUBLIC, tmp_path / "public"))
    ids = [c.id for c in READ.index().products if c.id.startswith("prd_w")][:len(summaries)]
    said = {pid: {"en": text} for pid, text in zip(ids, summaries)}
    for pid, summary in said.items():
        path = public / "products" / f"{pid}.json"
        path.write_text(json.dumps({**json.loads(path.read_text()), "summary": summary}))
    index = json.loads((public / "index.json").read_text())
    index["products"] = [{**c, "summary": said[c["id"]]} if c["id"] in said else c for c in index["products"]]
    (public / "index.json").write_text(json.dumps(index))
    engine = _engine(stores.blobs(), read=FilesCatalogRepository(public, MODEL))
    engine.index("rebuild")
    return engine, ids

def test_words_rank_by_stem_then_neighbours_then_rarity(tmp_path: Path) -> None:
    engine, (apart, near, *_, rare) = _summarised(tmp_path, [
        "a scan by the camera, then a long belt, a sorter and a production line", "a line scan camera",
        *["a camera"] * 8, "a barcode reader"])
    assert [h.card.id for h in _words("line scan", engine)][0] == near != apart
    assert _words("camera for barcodes", engine)[0].card.id == rare

def test_why_never_lists_a_stopword_and_a_summary_finds_its_product_in_english_and_french() -> None:
    for query in ("the widget with a glossy finish", "le widget à finition brillante",
                  "which widget replaces Widget Two"):
        hits = _words(query)
        assert hits and not {t for h in hits for m in h.why for t in m.terms} & set(CONFIG.stopwords)
    for query in ("glossy finish", "finition brillante"):
        assert _words(query)[0].card.name == "Widget Two"

def test_weak_matches_fall_under_the_cut_and_the_blend_adds_one_over_k_plus_each_rank() -> None:
    words = _words("widget glossy finish")
    assert len(words) < len(READ.index().products)
    assert all(h.score >= CONFIG.relative_cut * words[0].score for h in words)
    ranks = {h.card.id: n for n, h in enumerate(_words("widget"), 1)}
    blended = FX.search_engine.search(SearchRequest("widget", None, semantic=True))
    meaning = [h.score - (1 / (CONFIG.rrf_k + ranks[h.card.id]) if h.card.id in ranks else 0) for h in blended]
    assert all(any(abs(m - 1 / (CONFIG.rrf_k + r)) < 1e-12 for r in range(1, len(blended) + 1)) for m in meaning)

def test_an_id_a_slug_an_alias_a_category_label_and_a_spec_alias_each_find_theirs() -> None:
    index, views = READ.index(), {v.id: v for v in READ.products([c.id for c in READ.index().products])}
    target = index.products[-1]
    assert [_words(q)[0].card.id for q in (target.id, target.slug)] == [target.id] * 2
    for alias in ALIASES:
        hits = _words(alias["value"])
        expected = {alias["subject"]} if alias["subject"] in views else {
            v.id for v in views.values() if v.vendor.id == alias["subject"]}
        assert hits and ({hits[0].card.id} if alias["subject"] in views else {h.card.id for h in hits}) <= expected
    category = next(c for c in index.categories if c.products)
    for language in ("en", "fr"):
        hits = _words(category.label[language])
        assert {h.card.category for h in hits} == {category.id} and any(m.field == "category" for m in hits[0].why)
    spec = next(s for s in REGISTRY.spec_definitions.values() if s.aliases)
    published = {v.id for v in views.values() for c in (*v.core, *v.detail) if c.key == spec.id and c.value}
    assert all({h.card.id for h in _words(alias)} == published for alias in spec.aliases)
