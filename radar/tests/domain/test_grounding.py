from __future__ import annotations

import re

from radar.domain.search.retriever import IndexRetriever
from radar.domain.ai.answerer import Answerer
from radar.domain.ports.ai.answer_model import Sentence
from radar.tests.adapters.test_answers import FX, READ, REGISTRY, Scripted

def test_a_figure_of_one_product_cited_under_another_refuses_the_answer() -> None:
    retriever = IndexRetriever(FX.search_engine, READ, REGISTRY)
    products = retriever.evidence("widget", "en").products
    held = {p.id: {d for t in (p.id, p.name, p.summary, *(x for f in p.facts for x in (f.label, f.value)),
                               *(s.title for s in p.sources)) for d in re.findall(r"\d+", t)} for p in products}
    figure, cited = next((d, q.id) for p in products for d in sorted(held[p.id]) if len(d) > 1 for q in products
                         if d not in held[q.id])
    asked = Answerer(retriever, Scripted(Sentence(f"It reaches {figure}.", (cited,)))).ask("widget", "en")
    assert asked.answer.refused and asked.rejected == f"sentence 1 states {figure}, which what it cites does not hold"
