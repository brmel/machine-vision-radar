from __future__ import annotations

from typing import Mapping
from urllib.parse import urlsplit

import pytest

from radar.adapters.web.pages import PoliteFetcher
from radar.domain.ports.web.page_fetcher import Unfetchable
from radar.tests.adapters.stub_server import serving
from radar.tests.fixtures.fixture_category import recorded_page
from radar.tests.store import stores

DOCUMENTS = stores.fixture().model.registry.vocabularies["document_kinds"]
NOW, SITE = stores.NOW, "https://example.com"
SPECS = ('<!doctype html><html><head><title>Widget Ten</title><meta property="og:image" '
         'content="/media/widget-ten.jpg"></head><body>'
         '<img src="/media/logo.svg"><h1>Widget Ten</h1><p>A reach of up to <b>140</b> mm,\n in two finishes.</p>'
         '<table><tr><th>Model</th><th>Reach</th></tr><tr><td>WT-1</td><td>120 '
         'mm</td></tr><tr><td>WT-2</td><td><span>140</span> mm</td></tr></table>'
         '<ul><li>Matte</li><li>Gloss</li></ul><script>var tracking = 1;</script></body></html>')

def test_the_fetcher_reads_a_page_as_its_reader_sees_it() -> None:
    def page(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        return ((200, {"Content-Type": "text/html"}, SPECS.encode())
                if path == "/products/widget%20ten?model=Widget%20Ten&finish=%C3%BC" else recorded_page(path, headers))

    with serving(pages=page) as base:
        read = PoliteFetcher(f"{SITE}/about", lambda: NOW, DOCUMENTS, base, lambda: 0.0, lambda wait: None).fetch(
            f"{SITE}/products/widget ten?model=Widget%20Ten&finish=ü", 40.0)
    assert read.title == "Widget Ten"
    assert read.text.splitlines() == ["Widget Ten", "A reach of up to 140 mm, in two finishes.", "Model | Reach",
                                      "WT-1 | 120 mm", "WT-2 | 140 mm", "Matte", "Gloss"]
    assert read.images == (f"{SITE}/media/widget-ten.jpg", f"{SITE}/media/logo.svg")

def test_the_fetcher_reads_no_host_whose_name_resolves_to_a_private_address() -> None:
    heard: list[str] = []

    def page(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        heard.append(path)
        return recorded_page(path, headers)

    with serving(pages=page) as local:
        fetcher = PoliteFetcher(f"{SITE}/about", lambda: NOW, DOCUMENTS)
        for url in (f"http://localhost:{urlsplit(local).port}/", local):
            with pytest.raises(Unfetchable, match="is not a public address"):
                fetcher.fetch(url, 40.0)
    assert heard == []

def test_the_fetcher_reads_only_a_file_of_a_media_type_a_document_kind_lists() -> None:
    with serving(pages=recorded_page) as base:
        fetcher = PoliteFetcher(f"{SITE}/about", lambda: NOW, DOCUMENTS, base, lambda: 0.0, lambda wait: None)
        assert fetcher.file(f"{SITE}/media/widget-two.pdf", 40.0).mime == "application/pdf"
        with pytest.raises(Unfetchable, match="not a document: HTTP 200, text/html"):
            fetcher.file(f"{SITE}/", 40.0)
