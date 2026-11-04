from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from radar.adapters.firestore import layout
from radar.adapters.firestore.repository import StoreChangeLog
from radar.adapters.firestore.ledgers.ai import FirestoreUsageLog
from radar.adapters.wiring.root import Wiring
from radar.domain.ai.budget import Use
from radar.domain.ai.meter import Meter
from radar.domain.ports.ai.answer_model import Sentence
from radar.domain.ports.ai.article_model import ArticleText
from radar.domain.ports.search.retriever import Evidence
from radar.domain.review.feed.drafter import Drafter, drafted
from radar.domain.review.requests import Founder
from radar.adapters.storage.memory_change_log import MemoryChangeLog
from radar.domain.ports.history.change_log import ChangePage
from radar.domain.search.retriever import evidence_of
from radar.tests.store import stores

FX = stores.fixture()
PRODUCT, SOURCE = FX.rows("products.jsonl")[0]["id"], FX.rows("sources.jsonl")[0]["id"]

def _article(tmp_path: Path, title: str) -> str:
    body = [{"text": {"en": f"{title} cites a widget.", "fr": f"{title} cite un widget."}, "cites": [PRODUCT, SOURCE]}]
    return stores.file(tmp_path, f"{title}.json",
                       {"title": {"en": title, "fr": f"{title} (fr)"}, "summary": {"en": "A test article."},
                        "body": body})

def _public(place: tuple[str, str]) -> list[str]:
    feed = stores.fresh_at(place[0]).get(f"{layout.INDEX}/news")
    return [b["slug"] for b in json.loads(feed["json"])["items"]] if feed else []

def test_articles_are_drafted_reordered_published_revised_and_retracted(tmp_path: Path) -> None:
    place = FX.loaded()
    before = _public(place)
    first = FX.json(place, "feed", "new", _article(tmp_path, "First words"))["proposals"][0]["subject"]
    second = FX.json(place, "feed", "new", _article(tmp_path, "Second words"))["proposals"][0]["subject"]
    assert [d["id"] for d in FX.json(place, "feed", "list")["drafts"]] == [first, second] and _public(place) == before
    FX.json(place, "feed", "reorder", second, "1")
    assert [d["id"] for d in FX.json(place, "feed", "list")["drafts"]] == [second, first]
    assert FX.json(place, "feed", "publish", "--note", "Second first")["proposals"][0]["status"] == "approved"
    FX.json(place, "feed", "publish", "--note", "Then the first")
    listed = FX.json(place, "feed", "list")
    assert listed["drafts"] == [] and [p["id"] for p in listed["published"][:2]] == [first, second]
    assert _public(place) == ["first-words", "second-words", *before]

    shared = FX.json(place, "feed", "share-text", "first-words", "--locale", "fr")
    assert (shared["url"].endswith("/news/first-words")
            and shared["text"].splitlines() == ["First words (fr)", "A test article.", shared["url"]])
    FX.json(place, "feed", "edit", first, _article(tmp_path, "First words again"), "--note", "A better title")
    assert FX.json(place, "feed", "show", first)["title"]["en"] == "First words again"
    assert [v["version"] for v in FX.json(place, "record", "history", first)["versions"]][:2] == [2, 1]

    FX.json(place, "feed", "retract", "first-words", "--note", "Withdrawn")
    assert (_public(place) == ["second-words", *before]
            and stores.fresh_at(place[0]).get(f"{layout.NEWS}/first-words") is None)
    assert [v["version"] for v in FX.json(place, "record", "history", first)["versions"]] == [3, 2, 1]
    assert (FX.json(place, "record", "diff", first, "1", "2")["changes"]
            and stores.cli(FX, place, "record", "history", "nws_zzzzzzzzzz", check=False).returncode == 1)
    third = FX.json(place, "feed", "new", _article(tmp_path, "First words"))["proposals"][0]["subject"]
    assert FX.json(place, "feed", "show", third)["slug"] == "first-words-2"

def test_a_product_an_article_cites_is_not_withdrawn_from_under_it() -> None:
    place = FX.loaded()
    article = next(i for i in FX.rows("feed_items.jsonl") if any(c.startswith(PRODUCT[:4]) for c in i["cites"]))
    cited = next(c for c in article["cites"] if c.startswith(PRODUCT[:4]))
    refused = stores.cli(FX, place, "product", "retract", cited, "--reason", "No longer made", check=False)
    assert refused.returncode == 1 and article["id"] in refused.stderr

def test_the_admin_news_routes_answer_what_the_commands_print(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    place = FX.loaded()
    FX.wire(place, monkeypatch)
    wiring = Wiring()
    route = wiring.news_admin(wiring.review()).route

    def call(method: str, *parts: str, body: dict[str, Any] | None = None, **query: str) -> tuple[int, Any]:
        found = route(method, parts, query, body or {}, Founder("founder@example.com", "admin-test"))
        assert found is not None, f"no route {method} {'/'.join(parts)}"
        return found.status, found.body

    article = json.loads(Path(_article(tmp_path, "Routed words")).read_text())
    status, filed = call("POST", body={"article": article})
    assert status == 201 and call("GET") == (200, FX.json(place, "feed", "list"))
    assert call("POST", filed["subject"], "move", body={"position": 1})[1] == {"proposals": []}
    assert call("POST", "publish", body={"note": "Out"})[1]["status"] == "approved"
    assert call("GET", "routed-words", "share", locale="fr")[1] == FX.json(
        place, "feed", "share-text", "routed-words", "--locale", "fr")
    assert call("POST", "routed-words", "retract", body={"note": "Withdrawn"})[1]["subject"] == filed["subject"]
    assert call("GET") == (200, FX.json(place, "feed", "list"))

def test_the_change_log_lists_every_change_after_a_cursor_in_order() -> None:
    docs, files = FX.seeded()
    store = StoreChangeLog(docs, FX.schema)
    for log in (store, MemoryChangeLog(store.after().changes)):
        every = log.after()
        keys = [(c.recorded_at, c.id) for c in every.changes]
        assert keys == sorted(keys) and len(keys) == sum(1 for _ in docs.list(layout.CHANGES)) > 2
        half = every.changes[len(keys) // 2]
        assert log.after(f"{half.recorded_at}|{half.id}") == ChangePage(
            every.changes[len(keys) // 2 + 1:], every.cursor)
        assert log.after(every.cursor) == ChangePage((), every.cursor)

def _created(row: dict[str, Any], n: int, **fields: Any) -> dict[str, Any]:
    return {**{k: v for k, v in row.items() if k != "version"}, "id": f"{row['id'][:4]}00000000z{n}", **fields}

def test_the_detector_drafts_the_digest_then_the_significant_changes(tmp_path: Path) -> None:
    place = FX.loaded()
    digest = FX.json(place, "feed", "detect")["proposals"]
    shown = FX.json(place, "feed", "show", digest[0]["subject"])
    assert (len(digest) == 1 and shown["authorship"] == "template"
            and str(len(FX.rows("organizations.jsonl"))) in shown["title"]["en"])
    assert FX.json(place, "feed", "detect")["proposals"] == []
    FX.json(place, "proposal", "approve", digest[0]["id"], "--note", "The launch digest")
    listed = FX.json(place, "feed", "list")
    assert (listed["drafts"] == [] and listed["published"][0]["id"] == digest[0]["subject"]
            and listed["published"][0]["published_at"])

    product, name, role = (FX.rows(f)[2] for f in ("products.jsonl", "names.jsonl", "product_org_roles.jsonl"))
    made = [(_created(product, n, slug=f"{product['slug']}-made-{n}"),
             _created(name, n, subject=f"prd_00000000z{n}", value=f"Made {n}"),
             _created(role, n, product=f"prd_00000000z{n}")) for n in (1, 2)]
    changes = [stores.put(r, "New in the catalog", role["source_refs"]) for trio in made for r in trio]
    stores.cli(FX, place, "change", "apply", stores.changes_file(tmp_path, "two.json", *changes))
    batched = FX.json(place, "feed", "detect")["proposals"]
    assert len(batched) == 1 and len(FX.json(place, "feed", "show", batched[0]["subject"])["body"]) == 2

    version = _created(FX.rows("product_versions.jsonl")[0], 1, label="9.0.0", supersedes=None)
    stores.cli(FX, place, "change", "apply",
               stores.changes_file(tmp_path, "version.json",
                                   stores.put({k: v for k, v in version.items() if v}, "Released")))
    dated = FX.json(place, "feed", "show", FX.json(place, "feed", "detect")["proposals"][0]["subject"])
    assert (dated["event_date"], dated["event_source"]) == (version["released"], version["source_refs"][0])
    pair = [_created(FX.rows("product_versions.jsonl")[0], n, label=f"9.{n}.0", supersedes=None) for n in (2, 3)]
    stores.cli(FX, place, "change", "apply",
               stores.changes_file(tmp_path, "pair.json",
                                   *(stores.put({k: v for k, v in ver.items() if v}, "Released") for ver in pair)))
    batched_versions = FX.json(place, "feed", "show", FX.json(place, "feed", "detect")["proposals"][0]["subject"])
    assert (len(batched_versions["body"]) == 2 and "event_date" not in batched_versions
            and "event_source" not in batched_versions)

    trio = (_created(product, 3, slug=f"{product['slug']}-made-3"),
            _created(name, 3, subject="prd_00000000z3", value="Made 3"), _created(role, 3, product="prd_00000000z3"))
    imported = [{**stores.put(r, "Imported", role["source_refs"]), "actor_kind": "import"} for r in trio]
    stores.cli(FX, place, "change", "apply", stores.changes_file(tmp_path, "import.json", *imported))
    assert FX.json(place, "feed", "detect")["proposals"] == []
    published = FX.json(place, "feed", "approve", "--all-proposed", "--note", "The templated batch")["proposals"]
    assert len(published) == 3 and FX.json(place, "feed", "list")["drafts"] == []

def _drafts(place: tuple[str, str]) -> list[str]:
    return [d["id"] for d in FX.json(place, "feed", "list")["drafts"]]

def test_the_article_model_drafts_about_a_product_or_an_organization_under_the_draft_cap(tmp_path: Path) -> None:
    place = FX.loaded()
    vendor = next(c["vendor"] for c in FX.index["products"] if c["id"] == PRODUCT)
    org = next(o["id"] for o in FX.index["organizations"] if o["slug"] == vendor)
    drafts = [FX.json(place, "feed", "draft", item, "--ai")["proposals"][0]["subject"] for item in (PRODUCT, vendor)]
    assert _drafts(place)[-2:] == drafts
    for item, draft in zip((PRODUCT, org), drafts):
        shown = FX.json(place, "feed", "show", draft)
        assert (shown["authorship"] == "ai_draft" and 3 <= len(shown["body"]) <= 5
                and {s["cites"][0] for s in shown["body"]} == {item})
    cap = {**next(c for c in FX.rows("ai_caps.jsonl") if c["use"] == Use.DRAFT.value), "day_calls": 2}
    stores.cli(FX, place, "change", "apply",
               stores.changes_file(tmp_path, "cap.json", stores.put(cap, "Two drafts a day")))
    refused = stores.cli(FX, place, "feed", "draft", PRODUCT, "--ai", check=False)
    assert (refused.returncode == 1 and f"{Use.DRAFT.value}: 2 calls a day, made" in refused.stderr
            and _drafts(place)[-2:] == drafts)

@dataclass(frozen=True)
class Stating:
    sentences: tuple[str, ...]
    summary: str = "A widget."

    def draft(self, subject: Evidence, about: str, locale: str) -> ArticleText:
        named = subject.products[0]
        return ArticleText(named.name, self.summary,
                           tuple(Sentence(s.format(name=named.name), (named.id,)) for s in self.sentences), 1, 1)

GROUNDED = ("{name} is a widget.", "{name} is in the catalog.", "{name} has a datasheet.")

def test_a_draft_resting_on_more_than_the_record_never_reaches_the_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    place = FX.loaded()
    FX.wire(place, monkeypatch)
    wiring, queued = Wiring(), FX.json(place, "proposal", "list")
    model = Stating((*GROUNDED[:2], "{name} reaches 9,999 mm."))
    meter = Meter(wiring.budget(), FirestoreUsageLog(wiring.store()), FX.registry.ai, Use.DRAFT, "draft",
                  lambda chosen: model)
    drafter = Drafter(wiring.retriever(wiring.search_engine()), wiring.repository(), wiring.feed(), meter,
                      lambda: wiring.now()[:10])
    with pytest.raises(ValueError, match="sentence 3 states 9999, which is not in the evidence"):
        drafter.draft(PRODUCT, "draft-test")
    assert FX.json(place, "proposal", "list") == queued

def test_a_draft_with_a_number_the_record_lacks_in_its_title_or_summary_is_refused() -> None:
    subject = evidence_of(FX.read.products([PRODUCT]), FX.registry, "en")
    assert "sentence 4 states 9999" in (
        drafted(Stating(GROUNDED, summary="A 9,999 mm widget."), subject, "", "en").rejected or "")
