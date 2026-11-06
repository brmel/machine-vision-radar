from __future__ import annotations

import json
from typing import Mapping

from radar.adapters.ai.scripted import ScriptedResearchAgent
from radar.domain.model.entities import AiModel
from radar.domain.ports.ai.research_agent import Findings, Reading
from radar.domain.ports.review.research_runs import Step
from radar.domain.review.agents.research.frontier import ProductScope
from radar.tests.adapters.web.test_research import FX, _run
from radar.tests.fixtures.fixture_category import recorded_page

PRODUCT = "prd_0000000002"
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
    assert any("labels no spec names: Colour of the box" in s for s in run.said(Step.SKIPPED))

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
