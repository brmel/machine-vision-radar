from __future__ import annotations

from typing import Mapping
from urllib.parse import urlsplit

from radar.adapters.web.pages import PoliteReader
from radar.domain.ports.web.reader import File, Link, Page, Unread
from radar.tests.adapters.stub_server import serving
from radar.tests.fixtures.fixture_category import recorded_page
from radar.tests.store import stores

DOCUMENTS = stores.fixture().model.registry.vocabularies["document_kinds"]
NOW, SITE, BY = stores.NOW, "https://example.com", "2026-10-18T12:00:40Z"
SPECS = ('<!doctype html><html><head><title>Widget Ten</title><meta property="og:image" '
         'content="/media/widget-ten.jpg"></head><body><svg><title>Icon-Contact</title></svg>'
         '<img src="/media/logo.svg"><h1>Widget Ten</h1><p>A reach of up to <b>140</b> mm,\n in two finishes.</p>'
         '<table><tr><th>Model</th><th>Reach</th></tr><tr><td>WT-1</td><td>120 '
         'mm</td></tr><tr><td>WT-2</td><td><span>140</span> mm</td></tr></table>'
         '<ul><li>Matte</li><li>Gloss</li></ul><a href="https://docs.example.com/widget-ten.webp"></a>'
         '<a href="mailto:sales@example.com"></a><script>var tracking = 1;</script></body></html>')
INDEX = (f'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
         f'<sitemap><loc>{SITE}/maps/models.xml</loc></sitemap><sitemap><loc>{SITE}/maps/gone.xml</loc></sitemap>'
         f'</sitemapindex>')
MODELS = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          '<url><loc>https://docs.example.com/models/wt-1?lang=en&amp;v=2</loc></url>'
          f'<url><loc>{SITE}/products/widget-two</loc></url></urlset>')

def _reader(base: str) -> PoliteReader:
    return PoliteReader(f"{SITE}/about", lambda: NOW, DOCUMENTS, base, lambda: 0.0, lambda wait: None)

def test_the_reader_reads_a_page_as_its_reader_sees_it() -> None:
    def page(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        return ((200, {"Content-Type": "text/html"}, SPECS.encode())
                if path == "/products/widget%20ten?model=Widget%20Ten&finish=%C3%BC" else recorded_page(path, headers))

    with serving(pages=page) as base:
        reader = _reader(base)
        link = reader.link("https://www.example.com/products/widget ten?model=Widget%20Ten&finish=ü")
        assert isinstance(link, Link) and link.site == "example.com", "a site is its host, without www"
        read = reader.page(link, BY)
    assert isinstance(read, Page) and read.link == link and read.title == "Widget Ten"
    assert read.text.splitlines() == ["Widget Ten", "A reach of up to 140 mm, in two finishes.", "Model | Reach",
                                      "WT-1 | 120 mm", "WT-2 | 140 mm", "Matte", "Gloss"]
    assert read.links == (Link("https://docs.example.com/widget-ten.webp", "docs.example.com"),), "web links only"
    assert [i.address for i in read.images] == ["https://www.example.com/media/widget-ten.jpg",
                                                "https://docs.example.com/widget-ten.webp"], (
        "its photos, linked or shown, never a drawing")

def test_the_reader_reads_no_host_whose_name_resolves_to_a_private_address() -> None:
    heard: list[str] = []

    def page(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        heard.append(path)
        return recorded_page(path, headers)

    with serving(pages=page) as local:
        reader = PoliteReader(f"{SITE}/about", lambda: NOW, DOCUMENTS)
        for url in (f"http://localhost:{urlsplit(local).port}/", local):
            link = reader.link(url)
            assert isinstance(link, Link)
            read = reader.page(link, BY)
            assert isinstance(read, Unread) and read.reason.endswith("is not a public address")
    assert heard == [] and reader.link("mailto:sales@example.com") == Unread("mailto:sales@example.com",
                                                                            "not a web address")

def test_the_reader_reads_only_a_file_of_a_media_type_a_document_kind_lists() -> None:
    with serving(pages=recorded_page) as base:
        reader = _reader(base)
        sheet, home = (reader.link(f"{SITE}{path}") for path in ("/media/widget-two.pdf", "/"))
        assert isinstance(sheet, Link) and isinstance(home, Link)
        file = reader.file(sheet, BY)
        assert isinstance(file, File) and file.mime == "application/pdf"
        assert reader.file(home, BY) == Unread(f"{SITE}/", "not a document: HTTP 200, text/html")

def test_the_reader_lists_the_pages_of_a_site_s_sitemaps_from_its_index() -> None:
    served = {"/robots.txt": f"User-agent: *\nSitemap: {SITE}/maps/index.xml\n", "/maps/index.xml": INDEX,
              "/maps/models.xml": MODELS}

    def mapped(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        found = served.get(path)
        return ((200, {"Content-Type": "text/plain" if path == "/robots.txt" else "application/xml"}, found.encode())
                if found else recorded_page(path, headers))

    with serving(pages=mapped) as base:
        home = _reader(base).link(f"{SITE}/")
        assert isinstance(home, Link)
        assert _reader(base).sitemap(home, BY) == (
            Link("https://docs.example.com/models/wt-1?lang=en&v=2", "docs.example.com"),
            Link(f"{SITE}/products/widget-two", "example.com")), "the index's child sitemaps, one missing"
    with serving(pages=recorded_page) as base:
        assert _reader(base).sitemap(home, BY) == (), "a site with no sitemap"
