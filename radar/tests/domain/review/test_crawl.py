from __future__ import annotations

from typing import Any, Mapping

from radar.adapters.firestore.ledgers.agents import FirestoreCrawlRecords
from radar.domain.model.entities import AiModel
from radar.domain.ports.ai.research_agent import Findings, Reading
from radar.domain.ports.review.research_runs import Step
from radar.domain.ports.store.docs import Docs
from radar.domain.ports.web.crawl_records import CrawlRecord, CrawlStatus, PageKind
from radar.tests.adapters.web.test_research import MAKER, SITE, _run, docs  # noqa: F401
from radar.tests.fixtures.fixture_category import recorded_page

PAGES = [f"/en/products/widget-{n}" for n in range(6)] + ["/en/about", "/fr/products/widget-0", "/en/news-1",
                                                          "/en/news-2", "/en/news-3"]
MAP = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
       + "".join(f"<url><loc>{SITE}{p}</loc></url>" for p in PAGES) + "</urlset>")

class Quiet:
    calls = 0

    def research(self, reading: Reading) -> Findings:
        Quiet.calls += 1
        return Findings((), (), 1, 1)

def _quiet(base: str, chosen: AiModel) -> Quiet:
    return Quiet()

def _site(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
    if path == "/sitemap.xml":
        return 200, {"Content-Type": "application/xml"}, MAP.encode()
    if path in PAGES:
        return 200, {"Content-Type": "text/html"}, f"<html><title>{path}</title><p>{path}</p></html>".encode()
    return recorded_page(path, headers)

def test_runs_read_a_maker_s_pages_in_order_continue_and_skip_what_has_not_changed(
        docs: tuple[Docs, Any]) -> None:  # noqa: F811
    first = _run(docs, [], [], serve=_site, agent=_quiet)
    read = first.said(Step.READ)
    assert [a.removeprefix(SITE) for a in read[1:7]] == [f"/en/products/widget-{n}" for n in range(6)], (
        "product pages first")
    held = {r.address: r for r in FirestoreCrawlRecords(docs[0]).listed(MAKER["id"])}
    assert f"{SITE}/fr/products/widget-0" not in held, "one language copy of a page"
    assert held[f"{SITE}/en/products/widget-0"].status is CrawlStatus.READ

    called = Quiet.calls
    second = _run(docs, [], [], serve=_site, agent=_quiet)
    pages = {f"{SITE}{p}" for p in PAGES if not p.startswith("/fr")}
    assert set(second.said(Step.READ)[1:]) == pages - set(read), "it continues where the first stopped"
    assert f"{read[0]}: unchanged since it was last read" in second.said(Step.SKIPPED)
    assert Quiet.calls - called == len(second.said(Step.READ)) - 1, "an unchanged page reaches no model"

def test_makers_with_a_page_due_come_oldest_first(docs: tuple[Docs, Any]) -> None:  # noqa: F811
    crawl = FirestoreCrawlRecords(docs[0])
    crawl.save([CrawlRecord(f"{SITE}/{org}", SITE, org, PageKind.OTHER, CrawlStatus.DUE, at)
                for org, at in (("org_b", "2026-10-02T00:00:00Z"), ("org_a", "2026-10-01T00:00:00Z"),
                                ("org_c", "2026-12-01T00:00:00Z"))])
    assert crawl.due("2026-11-01T00:00:00Z") == ("org_a", "org_b")
