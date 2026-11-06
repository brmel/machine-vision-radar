from __future__ import annotations

from typing import Mapping

import pytest

from radar.domain.model.entities import OrgRelation, Organization
from radar.domain.model.history.changeset import as_record
from radar.domain.ports.review.research_runs import Step
from radar.domain.review.agents.research.frontier import sites_of
from radar.tests.fixtures.fixture_category import CategoryScope, MakerScope, ProductScope
from radar.domain.review.agents.runs import run_view
from radar.tests.adapters.web.test_research import FX, MAKER, REGISTRY, SITE, _run
from radar.tests.fixtures.fixture_category import recorded_page

def test_a_scope_is_a_product_a_maker_or_a_category_with_a_website() -> None:
    orgs, index = [Organization(**o) for o in FX.rows("organizations.jsonl")], FX.read.index()
    owning = [OrgRelation(**r) for r in FX.rows("org_relations.jsonl")
              if REGISTRY.vocabularies["org_relation_types"][r["type"]].owns]
    [site] = sites_of(MakerScope(MAKER["id"]), orgs, owning, FX.read)
    assert sites_of(MakerScope(MAKER["slug"]), orgs, owning, FX.read) == (site,)
    assert (site.org, site.home, site.sites) == (MAKER["id"], SITE, (SITE, "https://nordwerk.example.com")), (
        "its own site and its owner's")
    assert [p.id for p in site.products] == [p.id for p in index.products if p.vendor == MAKER["slug"]] != []
    category = index.products[0].category
    assert {s.org for s in sites_of(CategoryScope(category), orgs, owning, FX.read)} == {
        o.id for o in orgs if o.website and any(p.vendor == o.slug and p.category == category for p in index.products)}
    [p_site] = sites_of(ProductScope("prd_0000000002"), orgs, owning, FX.read)
    assert (p_site.one_product, p_site.products[0].id, p_site.org, p_site.sites[1:]) == (
        True, "prd_0000000002", MAKER["id"], site.sites)
    for scope in (ProductScope(MAKER["slug"]), MakerScope("prd_0000000002"), CategoryScope(MAKER["slug"])):
        with pytest.raises(LookupError, match="no product|no organization|no category"):
            sites_of(scope, orgs, owning, FX.read)

def test_a_maker_run_reads_its_sitemaps_first_and_types_each_source_by_its_site() -> None:
    types = REGISTRY.vocabularies["source_types"]
    hosted, host = next((k, t.hosts[0]) for k, t in types.items() if t.hosts)
    own = next(k for k, t in types.items() if t.research)
    other = next(k for k, t in types.items() if t.third_party)
    sheet, private = f"https://{host}/media/widget-two.pdf", "https://elsewhere.example.org/media/widget-two.pdf"
    pages = (f"{SITE}/products/widget-two", "https://elsewhere.example.org/products/widget-ten",
             "https://docs.example.com/products/widget-nine")
    mapped = "".join(f"<url><loc>{page}</loc></url>" for page in pages)
    served = {"/": (200, {"Content-Type": "text/html"}, b"<title>Example Devices</title>"),
              "/sitemap.xml": (200, {"Content-Type": "application/xml"}, f"<urlset>{mapped}</urlset>".encode())}

    def serve(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        status, sent, body = served.get(path) or recorded_page(path, headers)
        if headers["Host"].startswith("elsewhere."):
            return status, sent, body.replace(b"socket_b", b"socket_a")
        moved = {'"/media/widget-two.pdf"': f'"{sheet}"', f"{SITE}/media/widget-two.pdf": sheet,
                 "http://169.254.169.254/latest/meta-data/": private}
        for was, now in moved.items():
            body = body.replace(was.encode(), now.encode())
        return status, sent, body

    docs = FX.seeded()
    run = _run(docs, [], [], serve=serve)
    assert run.said(Step.READ) == (f"{SITE}/", pages[2], pages[0]), (
        "its home, then its sitemap's pages on its sites, its documentation subdomain first")
    queue = FX.queue(docs[0])
    typed = {r["url"]: r["type"] for p in run_view(run).filed if (proposal := queue.get(p)) and proposal.changeset
             for r in map(as_record, (c.action.entity for c in proposal.changeset.changes if c.entity[:4] == "src_"))}
    assert typed == {pages[0]: own, pages[2]: own, sheet: hosted, private: other}, (
        "a page on the maker's sites is its own; a file off them is typed by its host, else as a third party's")
