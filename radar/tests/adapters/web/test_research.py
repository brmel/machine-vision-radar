from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Callable, Mapping, TypeVar

import pytest

from radar import paths
from radar.adapters.ai.prompted.research_agent import PromptedResearchAgent
from radar.adapters.ai.meta.runner import MetaRunner
from radar.adapters.ai.scripted import ScriptedDatasheetExtractor, ScriptedImageJudge, ScriptedResearchAgent
from radar.adapters.console import log
from radar.adapters.files.prompts import FilesPromptRegistry
from radar.adapters.firestore.repository import StoreCatalogRepository, StoreHeldRecords
from radar.adapters.firestore.ledgers.agents import FirestoreAgentTokens, FirestoreResearchRuns
from radar.adapters.firestore.ledgers.ai import CALLS, FirestoreBudget, FirestoreUsageLog
from radar.adapters.web.pages import PoliteReader
from radar.adapters.wiring.stores import Stores
from radar.domain.ai.budget import Use
from radar.domain.ai.meter import Meter
from radar.domain.model.entities import AiModel, FilesOn
from radar.domain.ports.ai.image_judge import ImageJudge
from radar.domain.ports.ai.research_agent import ResearchAgent
from radar.domain.ports.review.research_runs import ResearchRun, Status, Step
from radar.domain.model.history.changeset import Changeset, PutEntity, as_record, without_version
from radar.domain.ports.store.blob_store import BlobRef
from radar.domain.ports.store.docs import Docs
from radar.domain.review.agents.files import Files
from radar.domain.review.agents.research.filing import RESEARCHER
from radar.domain.review.agents.research.run import Researcher
from radar.domain.model.entities import RunScope
from radar.tests.fixtures.fixture_category import MakerScope, ProductScope
from radar.domain.review.agents.runs import run_view
from radar.domain.review.proposal import Proposal
from radar.domain.review.requests import Approval, Founder, Picked, Revision
from radar.tests.adapters.stub_server import Answer, Pages, meta_saying, serving
from radar.tests.fixtures.fixture_category import recorded_page
from radar.tests.store import stores

M = TypeVar("M")

FX = stores.fixture()
REGISTRY, NOW, SITE = FX.model.registry, stores.NOW, "https://example.com"
DOCUMENTS = REGISTRY.vocabularies["document_kinds"]
MAKER = next(o for o in FX.rows("organizations.jsonl") if o["website"] == SITE)
Heard = list[tuple[str, Mapping[str, str]]]

@pytest.fixture
def docs() -> tuple[Docs, Any]:
    return FX.seeded()

def _run(seeded: tuple[Docs, Any], heard: Heard, waits: list[float], on_get: Callable[[str], None] = lambda path: None,
         now: Callable[[], str] = lambda: NOW, serve: Pages = recorded_page,
         agent: Callable[[str, AiModel], ResearchAgent] = lambda base, chosen: ScriptedResearchAgent(),
         model: Answer | None = None,
         judge: Callable[[str, AiModel], ImageJudge] = lambda base, chosen: ScriptedImageJudge(),
         scope: RunScope = MakerScope(MAKER["slug"])) -> ResearchRun:
    docs, files = seeded

    def page(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        heard.append((path, headers))
        on_get(path)
        return serve(path, headers)

    def meter(use: Use, opened: Callable[[AiModel], M]) -> Meter[M]:
        return Meter(FirestoreBudget(docs, FX.model), FirestoreUsageLog(docs), REGISTRY.ai, use, "scripted", opened)

    with serving(model, pages=page) as base:
        researcher = Researcher(meter(Use.RESEARCH, lambda chosen: agent(base, chosen)),
                                meter(Use.IMAGE_JUDGE, lambda chosen: judge(base, chosen)),
                                PoliteReader(f"{SITE}/about", lambda: NOW, DOCUMENTS, base, lambda: 0.0, waits.append),
                                Files(files, meter(Use.DATASHEET, lambda chosen: ScriptedDatasheetExtractor()),
                                      REGISTRY.vocabularies), FX.review(docs, files), FirestoreResearchRuns(docs),
                                FirestoreAgentTokens(docs), StoreCatalogRepository(docs, FX.model),
                                StoreHeldRecords(docs, FX.model), FX.model, now)
        return researcher.status(researcher.start(scope, Founder("founder", Stores().correlate("research"))))

def test_a_run_reads_the_maker_s_public_pages_politely_and_files_through_review(
        docs: tuple[Docs, Any], capsys: pytest.CaptureFixture[str]) -> None:
    log.configure(json_mode=True)
    heard: Heard = []
    waits: list[float] = []
    run = _run(docs, heard, waits)

    assert [path for path, _ in heard] == ["/robots.txt", "/sitemap.xml", "/", "/widget-two", "/products/widget-two",
                                           "/media/widget-two.png", "/media/widget-two.pdf", "/products/widget-nine",
                                           "/account", "/widgets.pdf", "/partner"], \
        ("the site's sitemap, which it lacks, then the links the model names, but one off the site, one the page does "
         "not hold and a sixth, which a later page names again")
    assert ({h["User-Agent"] for _, h in heard} == {f"mvradar-research/1 (+{SITE}/about)"}
            and not {"Cookie", "Authorization"} & {k for _, h in heard for k in h})
    assert waits == [1.0] * (len(heard) - 1), "one host, a second between requests"
    assert (run.outcome and run.outcome.status, run.said(Step.READ)) == (
        Status.DONE, (f"{SITE}/", f"{SITE}/products/widget-two", f"{SITE}/products/widget-nine"))
    assert [d.split(": ", 1)[1] for d in run.said(Step.SKIPPED)] == [
        "169.254.169.254 is not a public address", "the store holds it", "robots.txt disallows it",
        "not public: it asks for a sign-in", "not a page: HTTP 200, application/pdf",
        "it redirects off its site, to https://elsewhere.example.org/"]
    not_linked, unparsed, refused, unheld = run.said(Step.REJECTED)
    assert (not_linked, unheld) == (f"{SITE}/media/not-linked.svg: not one of the page's links",
                                    f"{SITE}/widgets.pdf: the file is for none of the cards' products")
    assert unparsed.startswith("The maker's page lists Widget Nine: record_parse clm_") and "does not parse" in unparsed
    assert (refused.startswith("The maker's page lists Widget Nine: claim_values clm_")
            and refused.endswith("'chrome' is not in registry 'fixture_finishes'")), \
        "each value refused, by its id, and Widget Nine filed without them"
    assert run.cad > 0

    queue, view = FX.queue(docs[0]), run_view(run)
    filed = [queue.get(p) for p in view.filed]
    [token] = FirestoreAgentTokens(docs[0]).page()[0]
    assert (token.id, token.name, token.revoked_at) == (run.token, RESEARCHER, None), "the day's token, kept"
    assert {(p.actor_kind, p.author, p.token, p.status) for p in filed if p} == {
        ("agent", RESEARCHER, run.token, "suggested")}
    found = [f"{SITE}/media/widget-two.png", f"{SITE}/media/widget-two.pdf", f"{SITE}/media/widget-two.pdf"]
    assert [(p.files_on, p.source_url) for p in filed if p] == [
        (FilesOn.UPDATE, None), (FilesOn.UPDATE, None), *((FilesOn.UPDATE, url) for url in found),
        (FilesOn.UPDATE, None), (FilesOn.CREATE, None)]
    assert (view.media, view.datasheets) == (view.filed[2:4], view.filed[4:5]), (
        "the log counts two files staged and a datasheet read")
    changes = [p.changeset.changes for p in filed if p and p.changeset]
    assert all(as_record(c[0].action.entity)["retrieved_at"] == NOW for c in changes), "each rests on what it read"
    assert changes[0][0].entity == "src_0000000004", "a page the store holds a Source for is cited by that Source"
    assert [c.entity for c in changes[1][1:]] == ["clm_0000000003"], (
        "a value the page states otherwise corrects the claim the store ranks first")
    assert all(c.actor == RESEARCHER and c.source_refs == (read.entity,)
               and as_record(c.action.entity).get("source_refs", [read.entity]) == [read.entity]
               for read, *rest in changes for c in (read, *rest)), "every record cites the Source the proposal rests on"
    assert sum("source_refs" in as_record(c.action.entity) for p in changes for c in p) == 6, "five claims and a role"
    assert {as_record(c.action.entity)["spec_key"]: as_record(c.action.entity)["value"] for c in changes[-1]
            if as_record(c.action.entity).get("spec_key") in ("fixture_mount", "fixture_mass")} == {
        "fixture_mount": {"term": "socket_b"}, "fixture_mass": {"quantity": {"value": 140, "unit": "g"}}}, \
        "a term named by its label in a one-term set, and a unit by another spelling, are put by their ids"

    entries = [e for e in queue.log().entries if e.proposal in view.filed]
    calls = [f for _, f in docs[0].list(CALLS)]
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert len(entries) == 7 and {e.correlation_id for e in entries} == {run.id}
    assert len(calls) == 4 and {c["correlation_id"] for c in calls} == {run.id}
    assert (len([n for n in lines if n["event"].startswith("research: ")]) == len(run.lines) + 1
            and {n["correlation_id"] for n in lines} == {run.id})

def _on_runner(base: str, chosen: AiModel) -> ResearchAgent:
    runner = MetaRunner(chosen.id, f"{base}/v1", "recorded")
    return PromptedResearchAgent(FilesPromptRegistry(paths.PROMPTS).prompt("research"), runner, REGISTRY)

def test_a_reply_cut_short_refuses_its_page_and_counts_in_the_run_s_cost(docs: tuple[Docs, Any]) -> None:
    run = _run(docs, [], [], agent=_on_runner, model=meta_saying('{"proposals": [{"files_on": "upd', []))
    refused = run.said(Step.REJECTED)
    assert len(refused) == len(run.said(Step.READ)) > 0 and all("the model's answer is refused: research: " in r
                                                                for r in refused)
    assert run.said(Step.FILED) == () and run.cad > 0

def test_a_run_on_its_model_gives_it_the_catalog_s_terms_and_refuses_a_draft_naming_what_it_was_not_given(
        docs: tuple[Docs, Any]) -> None:
    card = next(p.id for p in FX.read.index().products if p.vendor == MAKER["slug"])
    model_id = "prd_0000000099"
    first = {name: next(iter(REGISTRY.vocabularies[name]))
             for name in ("product_kinds", "product_org_roles", "version_kinds")}
    unknown = [{"id": model_id, "kind": first["product_kinds"], "category": "lighting.displays.touch",
                "slug": "example-devices__touch"},
               {"id": "nam_touch", "subject": model_id, "value": "Touch", "is_primary": True},
               {"id": "por_touch", "product": model_id, "org": MAKER["id"], "role": first["product_org_roles"]}]
    stray = [{"id": "ver_fw", "product": "prd_scs", "kind": first["version_kinds"], "label": "2.1"}]
    said = {"proposals": [{"files_on": "create", "reason": "A touch display", "subject": model_id,
                           "records": json.dumps(unknown)},
                          {"files_on": "update", "reason": "A firmware", "subject": card,
                           "records": json.dumps(stray)}],
            "follow": [f"{SITE}/widget-two", f"{SITE}/products/widget-ten"]}
    heard: list[str] = []
    run = _run(docs, [], [], agent=_on_runner, model=meta_saying(json.dumps(said), heard))

    asked = json.loads(heard[0])["messages"][1]["content"][0]["text"]
    assert all(f'"{term}"' in asked for term in (*REGISTRY.categories, *REGISTRY.spec_definitions)), (
        "every category and spec key")
    assert '"slug*": []' in asked and '"name' not in asked.split('"Product"', 1)[1].split("}", 1)[0], (
        "every Product field, required ones marked")
    specs = json.loads(asked.split("The specs:\n", 1)[1].split("\n\nThe profiles", 1)[0])
    assert [s["id"] for s in specs] == ["fixture_reach", "fixture_finish", "fixture_mount", "fixture_mass",
                                        "fixture_label", "fixture_adapters"], (
        "the specs of the cards' categories only")
    assert ('\n{"fixture_domain.widgets": {"specs": ["fixture_reach", "fixture_finish", "fixture_mount", '
            '"fixture_mass", "fixture_label", "fixture_adapters"], '
            '"filters": ["fixture_finish", "fixture_reach", "fixture_mount"]}}\n') in asked, (
        "the profile of the cards' one category, its specs and filters")
    assert run.said(Step.READ) == (f"{SITE}/", f"{SITE}/products/widget-two"), "the link it names that the page holds"
    assert run.said(Step.FILED) == () and len(run.said(Step.REJECTED)) == 2 * len(run.said(Step.READ))
    ref, term = sorted(set(run.said(Step.REJECTED)))
    assert ref == ("A firmware: ProductVersion.product: prd_scs is none of the cards, the maker or the records of the "
                   "proposal")
    assert model_id not in term, "the model names a new record; one of our ids numbers it"
    assert (term.startswith("A touch display: ")
            and term.endswith("Product.category: 'lighting.displays.touch' is not in registry 'categories'"))

def test_a_file_is_staged_privately_and_public_only_once_approved_under_rights_that_allow_it() -> None:
    docs, files = seeded = FX.seeded()
    run = _run(seeded, [], [])
    queue, review, founder = FX.queue(docs), FX.review(docs, files), Founder("founder", "test")
    photo, sheet, stated = (queue.get(p) for p in (*run.said(Step.MEDIA), *run.said(Step.DATASHEET)))
    assert photo and sheet and stated and stated.changeset
    source, *claims = (as_record(c.action.entity) for c in stated.changeset.changes)
    assert (source["url"], [(c["subject"], c["spec_key"], c["method"], c["source_refs"]) for c in claims]) == (
        sheet.source_url, [(stated.subject, "fixture_mount", source["type"], [source["id"]])])

    def readable(proposal: Proposal) -> bool:
        document = next(as_record(c.action.entity) for c in (proposal.changeset.changes if proposal.changeset else ())
                        if c.entity.startswith("doc_"))
        url = files.url(BlobRef(document["sha256"], document["mime"]), True)
        return {200: True, 403: False}[stores.status("GET", url)]

    assert not readable(photo) and not readable(sheet), "staged privately"
    review.decide(Approval(Picked((photo.id,)), "The maker's photo"), founder).one()
    assert not readable(photo), "the maker's rights keep it private"
    public = next(k for k, t in REGISTRY.vocabularies["media_rights"].items() if t.public)
    opened = Changeset(tuple(replace(c, action=PutEntity(replace(c.action.entity, rights=public)))
                             if c.entity.startswith("doc_") else c for c in sheet.changeset.changes))
    review.decide(Revision(sheet.id, opened, "The maker licenses its datasheets openly"), founder).one()
    assert not readable(sheet), "an edit is not an approval"
    review.decide(Approval(Picked((sheet.id,)), "Checked"), founder).one()
    assert readable(sheet)

def test_the_research_cap_stops_a_run(docs: tuple[Docs, Any]) -> None:
    cap = next(c for c in FX.rows("ai_caps.jsonl") if c["use"] == Use.RESEARCH.value)
    FX.apply(*docs, "cap-test", stores.put({**cap, "day_calls": 1}, "One call a day"))
    run = _run(docs, [], [])
    assert (run.outcome
            and (run.outcome.status, run.said(Step.READ), run.outcome.reason) == (
                Status.CAPPED, (f"{SITE}/", f"{SITE}/products/widget-two"), "research: 1 calls a day, made"))
    assert run.said(Step.FILED) == ()

def test_the_time_budget_holds_between_the_files_of_one_page(docs: tuple[Docs, Any]) -> None:
    ticks = (f"2026-10-18T12:{n // 60:02d}:{n % 60:02d}Z" for n in range(0, 3600, 9))
    run = _run(docs, [], [], now=lambda: next(ticks))
    outcome = run.outcome and (run.outcome.status, run.outcome.reason)
    assert (run.said(Step.READ)[-1], len(run_view(run).filed), outcome) == (
        f"{SITE}/products/widget-two", 0, (Status.PARTIAL, "its 40 s are spent")), "stopped with pages left in reach"
    assert run.said(Step.SKIPPED), "the page's files past the budget are skipped, not fetched"

def test_the_judge_sees_the_photo_named_after_the_product_before_the_page_s_other_images(
        docs: tuple[Docs, Any]) -> None:
    def gallery(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        status, head, body = recorded_page(path, headers)
        return status, head, body.replace(b"</body>", b'<img src="/a.png"><img src="/b.png"><img src="/c.png">'
                                          b'<img src="/media/Widget-Two_L.jpg"></body>') if (
            path == "/products/widget-two") else body

    heard: Heard = []
    _run(docs, heard, [], scope=ProductScope("prd_0000000002"), serve=gallery)
    fetched = [path for path, _ in heard]
    assert "/media/Widget-Two_L.jpg" in fetched and "/c.png" not in fetched

def test_a_crawl_delay_longer_than_the_run_has_left_is_refused_not_waited(docs: tuple[Docs, Any]) -> None:
    def slow(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        return ((200, {"Content-Type": "text/plain"}, b"User-agent: *\nCrawl-delay: 600\n") if path == "/robots.txt"
                else recorded_page(path, headers))

    heard: Heard = []
    waits: list[float] = []
    run = _run(docs, heard, waits, serve=slow)
    assert (run.outcome and run.outcome.status, run.said(Step.READ), [path for path, _ in heard], waits) == (
        Status.BLOCKED, (), ["/robots.txt"], [])
    assert run.said(Step.SKIPPED) == (f"{SITE}/: its crawl delay of 600 s would pass the run's time",) * 2, (
        "neither its sitemap nor its page")

def test_a_cancel_stops_the_run_at_its_next_step(docs: tuple[Docs, Any]) -> None:
    runs = FirestoreResearchRuns(docs[0])

    def cancelling(path: str) -> None:
        if path == "/products/widget-two":
            runs.cancel(runs.page().runs[0].id, NOW)

    run = _run(docs, [], [], cancelling)
    assert (run.outcome and run.outcome.status, run.said(Step.READ), len(run_view(run).filed)) == (
        Status.CANCELLED, (f"{SITE}/", f"{SITE}/products/widget-two"), 6)

def test_a_product_run_proposes_the_best_photo_privately_and_what_the_page_states(docs: tuple[Docs, Any]) -> None:
    heard: Heard = []
    waits: list[float] = []
    run = _run(docs, heard, waits, scope=ProductScope("prd_0000000002"))
    assert run.outcome and run.outcome.status is Status.DONE and run.said(Step.READ) == (f"{SITE}/products/widget-two",)
    assert [len(run.said(s)) for s in (Step.FILED, Step.MEDIA, Step.DATASHEET)] == [4, 1, 1] and run.cad > 0
    assert "The maker's page shows a photo of Widget Two: an open proposal holds it" in run.said(Step.SKIPPED), (
        "the judged photo, not twice")
    assert "/media/widget-two.svg" not in [path for path, _ in heard], "the page's SVG is never sent to the judge"
    prop, *stated = (FX.queue(docs[0]).get(p) for p in run.said(Step.FILED))
    assert stated[-1] and stated[-1].changeset and stated[-1].reason == "This is Widget Two's own page"
    [own] = (as_record(c.action.entity) for c in stated[-1].changeset.changes if c.entity == "prd_0000000002")
    held = next(p for p in FX.rows("products.jsonl") if p["id"] == "prd_0000000002")
    assert own == {**without_version(held), "website_url": f"{SITE}/products/widget-two"}, "its summary kept"
    assert "The page names Widget Two: the store holds it" in run.said(Step.SKIPPED), "a held record is not filed again"
    assert prop is not None and prop.subject == "prd_0000000002" and "Widget Two" in prop.reason
    assert prop.changeset is not None
    doc = next(as_record(c.action.entity) for c in prop.changeset.changes if c.entity.startswith("doc_"))
    research = next(k for k, t in REGISTRY.vocabularies["media_rights"].items() if t.research)
    assert doc["rights"] == research, "a maker's photo is never labelled with a public right"
    assert all(c.entity != "prd_0000000002" for c in prop.changeset.changes), "nor made a thumbnail without one"
