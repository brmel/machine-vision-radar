from __future__ import annotations

from typing import Mapping, Sequence

from radar.domain.model.entities import (ProductView, ViewValue, ViewValueBoolean, ViewValueNone, ViewValueQuantity,
                                         ViewValueRange, ViewValueString, ViewValueTerm, ViewValueTerms)
from radar.domain.model.registry import Registry
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.search.retriever import Evidence, EvidenceProduct, Fact, SourceRef
from radar.domain.read_model.facets import js_number
from radar.domain.ports.search.search_engine import SearchEngine, SearchRequest

def _localized(text: Mapping[str, str], locale: str) -> str:
    return text.get(locale) or next(iter(text.values()), "")

def value_text(value: ViewValue, locale: str) -> str:
    match value:
        case ViewValueQuantity(quantity=q):
            return " ".join(filter(None, (js_number(q.value), q.unit)))
        case ViewValueRange(range=r):
            return " ".join(filter(None, (f"{js_number(r.min)}–{js_number(r.max)}", r.unit)))
        case ViewValueTerm(term=t):
            return _localized(t.label, locale)
        case ViewValueTerms(terms=ts):
            return ", ".join(_localized(t.label, locale) for t in ts)
        case ViewValueBoolean(boolean=b):
            return "yes" if b else "no"
        case ViewValueString(string=text):
            return text
        case ViewValueNone(none=reason):
            return _localized(reason.label, locale)
    return ""

def evidence_of(views: Sequence[ProductView], registry: Registry, locale: str) -> Evidence:
    out = []
    for v in views:
        facts = tuple(Fact(_localized(registry.spec_definitions[c.key].label, locale), value_text(c.value, locale),
                           c.source)
                      for c in (*v.core, *v.detail) if c.value is not None)
        sources = tuple(SourceRef(s.id, s.title or _localized(s.type.label, locale), s.url) for s in v.sources)
        category = registry.categories[v.category].label
        out.append(EvidenceProduct(v.id, v.name, v.vendor.name, _localized(category, locale),
                                   _localized(v.summary, locale) if v.summary else "", facts, sources))
    return Evidence(tuple(out))

class IndexRetriever:
    def __init__(self, engine: SearchEngine, read_model: CatalogRepository, registry: Registry) -> None:
        self._engine, self._read_model, self._registry = engine, read_model, registry

    def evidence(self, question: str, locale: str) -> Evidence:
        hits = self._engine.search(SearchRequest(question, self._registry.search.evidence))
        return self.about(tuple(h.card.id for h in hits), locale)

    def about(self, products: tuple[str, ...], locale: str) -> Evidence:
        return (evidence_of(self._read_model.products(list(products)), self._registry, locale) if products
                else Evidence(()))
