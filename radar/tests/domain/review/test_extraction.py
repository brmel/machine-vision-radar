from __future__ import annotations

import json
from typing import Mapping

from radar.adapters.ai.scripted import ScriptedResearchAgent
from radar.adapters.files.model_json import load_model
from radar.domain.model.entities import AiModel, ProductCard
from radar.domain.ports.ai.research_agent import Findings, Reading
from radar.domain.ports.review.research_runs import Step
from radar.domain.ports.web.reader import Link, Page
from radar.domain.review.agents.drafts import words
from radar.domain.review.agents.research.tables import Tables, named_card
from radar.tests.adapters.web.test_research import FX, _run
from radar.tests.fixtures.fixture_category import recorded_page
from radar.tests.fixtures.fixture_category import ProductScope

PRODUCT = "prd_0000000002"
ACCESSORIES = "accessories"
TABLE = ("<table><tr><th>Mass</th><td>Approx. 93 g</td></tr>"
         "<tr><th>Reach</th><td>(1)</td><td>(mm)</td><td>125</td></tr>"
         "<tr><th>Finish</th><td>Gloss</td></tr><tr><th>Mount</th><td>&lt;Socket B</td></tr>"
         "<tr><th>Colour of the box</th><td>Blue</td></tr></table>")
LINKED = {"@type": "Product", "additionalProperty": [{"name": "Body｜Mass", "value": "93 g"},
                                                       {"name": "Reach", "value": "125 mm"},
                                                       {"name": "Finish", "value": "Gloss"}]}

class Unreachable:
    def research(self, reading: Reading) -> Findings:
        raise AssertionError("the table answered: no model call")

def _serving(body: str, title: str = "Widget Two"):
    def serve(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        if path == "/products/widget-two":
            page = f"<!doctype html><html><head><title>{title}</title></head><body><h1>Widget</h1>{body}</body></html>"
            return 200, {"Content-Type": "text/html"}, page.encode()
        return recorded_page(path, headers)
    return serve

def _filed(docs, run) -> dict[str, object]:
    queue = FX.queue(docs[0])
    proposals = [queue.get(p) for p in run.said(Step.FILED)]
    return {c.action.entity.spec_key: c.action.entity.value for p in proposals if p and p.changeset
            for c in p.changeset.changes if c.entity.startswith("clm_")}

def _no_model(base: str, chosen: AiModel) -> Unreachable:
    return Unreachable()

def test_a_page_s_table_files_its_values_with_no_model_call_and_keeps_the_labels_no_spec_names() -> None:
    docs = FX.seeded()
    run = _run(docs, [], [], serve=_serving(TABLE), agent=_no_model, scope=ProductScope(PRODUCT))
    filed = _filed(docs, run)
    assert set(filed) == {"fixture_mass", "fixture_reach"}, "a bound files nothing, and the store holds its finish"
    assert filed["fixture_mass"].quantity.value == 93 and filed["fixture_reach"].quantity.value == 125
    assert any("Colour of the box" in s for s in run.said(Step.UNMATCHED))

def test_schema_org_properties_are_read_as_a_table() -> None:
    docs = FX.seeded()
    script = f'<script type="application/ld+json">{json.dumps(LINKED)}</script>'
    run = _run(docs, [], [], serve=_serving(script), agent=_no_model, scope=ProductScope(PRODUCT))
    assert set(_filed(docs, run)) == {"fixture_mass", "fixture_reach"}

def test_a_page_naming_no_card_or_too_little_goes_to_the_model() -> None:
    called = []

    class Noting(ScriptedResearchAgent):
        def research(self, reading: Reading) -> Findings:
            called.append(reading.page.link.address)
            return super().research(reading)

    little = "<table><tr><th>Mass</th><td>93 g</td></tr></table>"
    for body, title in ((TABLE, "An index of widgets"), (little, "Widget Two")):
        called.clear()
        _run(FX.seeded(), [], [], serve=_serving(body, title), agent=lambda base, chosen: Noting(),
             scope=ProductScope(PRODUCT))
        assert any(a.endswith("/products/widget-two") for a in called)

def _maker_rows(category: str, *rows: str) -> dict[str, object]:
    registry = load_model().registry
    page = Page(Link("https://maker.example/p", "maker.example"), "P-1", "\n".join(rows), (), (), "")
    card = ProductCard(id="prd_1", slug="m__p-1", name="P-1", kind="model", vendor="m", vendor_name="M",
                       category=category, specs={})
    return dict(Tables(registry, words(registry)).read(page, card).claims)

def test_rows_as_makers_write_them() -> None:
    lens = _maker_rows("optics.lenses", "Max sensor size | | 1/1.2″", "Focal point | 4.5 mm 0.18\"",
                       "Operating temperature and humidity | 0 to 40°C, 20 to 80% RH")
    assert lens == {"max_sensor_format": {"term": "1_1_2in"},
                    "focal_length": {"quantity": {"value": 4.5, "unit": "mm"}},
                    "operating_temperature": {"range": {"min": 0.0, "max": 40.0, "unit": "deg_c"}}}
    light = _maker_rows("optics.lighting", "Supply voltage (2) | (V) | 24", "Height | (mm) | 10")
    assert light == {"supply_voltage": {"quantity": {"value": 24.0, "unit": "v"}},
                     "body_height": {"quantity": {"value": 10.0, "unit": "mm"}}}
    assert _maker_rows("optics.lighting", "Relative humidity | 35 to 85 %RH (No condensation)") == {
        "operating_humidity": {"range": {"min": 35.0, "max": 85.0, "unit": "percent"}}}
    assert _maker_rows("optics.lighting", "Operating relative humidity | (%) | 20-85, non condensing") == {
        "operating_humidity": {"range": {"min": 20.0, "max": 85.0, "unit": "percent"}}}
    assert _maker_rows("imaging.cameras.area_scan", "Interface | 2.5GigE") == {"interfaces": {"terms": ["2_5gige"]}}
    assert _maker_rows("imaging.cameras.area_scan", "Interface | 25GigE") == {"interfaces": {"terms": ["25gige"]}}
    camera = _maker_rows("imaging.cameras.area_scan", "Sensor model | | IMX265", "Exposure time | 12 μs to 10 ms",
                         "Frame rate | 9.5 fps", "Pixel size | 2 x 3 µm", "Weight | 90 g", "Weight | 95 g")
    assert camera == {"sensor_model": {"string": "IMX265"}, "frame_rate": {"quantity": {"value": 9.5, "unit": "hz"}}}, (
        "two figures, two dimensions and two rows that disagree state no one value")
    assert not _maker_rows("imaging.cameras.area_scan", "Image sensor | CMOS image sensor"), "a phrase, no part number"
    assert not _maker_rows(ACCESSORIES, "Length | 3 m"), "a cable's or a body's: the word alone does not say"

def test_a_page_names_a_card_by_whole_words() -> None:
    def card(name: str) -> ProductCard:
        return ProductCard(id=f"prd_{name}", slug=name, name=name, kind="model", vendor="m", vendor_name="M",
                           category="optics.lenses", specs={})

    def page(title: str) -> Page:
        return Page(Link("https://maker.example/p", "maker.example"), title, "", (), (), "")

    assert named_card(page("A1000 datasheet"), (card("A100"),)) is None
    assert named_card(page("Surface inspection"), (card("ace"),)) is None
    assert named_card(page("LDL2-434X30(A)｜CCS INC."), (card("LDL2-434X30(A)"),)) == card("LDL2-434X30(A)")
