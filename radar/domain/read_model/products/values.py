from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from radar.domain.model.entities import (ClaimValue, ClaimValueBoolean, ClaimValueNone, ClaimValueQuantity,
                                         ClaimValueRange, ClaimValueString, ClaimValueTerm, ClaimValueTerms, Source,
                                         SourceView, SpecDefinition, TermRef, ViewQuantity, ViewRange, ViewValue,
                                         ViewValueBoolean, ViewValueNone, ViewValueQuantity, ViewValueRange,
                                         ViewValueString, ViewValueTerm, ViewValueTerms)
from radar.domain.model.registry import Registry

@dataclass(frozen=True, slots=True)
class Terms:
    registry: Registry

    def term(self, vocab: str, term_id: str) -> TermRef:
        item = self.registry.items(vocab).get(term_id)
        if item is None:
            raise ValueError(f"term '{term_id}' is not in '{vocab}'")
        return TermRef(id=term_id, label=dict(item.label))

    def source_view(self, s: Source) -> SourceView:
        return SourceView(id=s.id, type=self.term("source_types", s.type), url=s.url, title=s.title,
                          retrieved_at=s.retrieved_at)

def _in_unit(spec: SpecDefinition, unit: str, terms: Terms) -> tuple[Callable[[float], float], str | None]:
    shown = spec.unit or unit

    def to(value: float) -> float:
        converted = terms.registry.converted(value, unit, shown)
        return converted if spec.precision is None else round(converted, spec.precision)
    return to, terms.registry.units[shown].symbol or None

def _published(v: ClaimValue, spec: SpecDefinition, terms: Terms) -> list[ViewValue]:
    vocab = spec.vocabulary or ""
    match v:
        case ClaimValueQuantity(quantity=q):
            to, symbol = _in_unit(spec, q.unit, terms)
            return [ViewValueQuantity(quantity=ViewQuantity(value=to(q.value), unit=symbol))]
        case ClaimValueRange(range=r):
            to, symbol = _in_unit(spec, r.unit, terms)
            return [ViewValueRange(range=ViewRange(min=to(r.min), max=to(r.max), unit=symbol))]
        case ClaimValueBoolean(boolean=b):
            return [ViewValueBoolean(boolean=b)]
        case ClaimValueString(string=text):
            return [ViewValueString(string=text)]
        case ClaimValueTerm(term=t):
            return [ViewValueTerm(term=terms.term(vocab, t))]
        case ClaimValueTerms(terms=ts):
            return [ViewValueTerm(term=terms.term(vocab, t)) for t in ts]
        case ClaimValueNone(none=reason):
            return [ViewValueNone(none=terms.term("absence_reasons", reason))]
    return []

def view_value(values: list[ClaimValue], spec: SpecDefinition, terms: Terms) -> ViewValue | None:
    found = [row for v in values for row in _published(v, spec, terms)]
    distinct = [f for i, f in enumerate(found) if f not in found[:i]]
    if not distinct:
        return None
    if spec.datatype == "term_set":
        return ViewValueTerms(terms=tuple(f.term for f in distinct if isinstance(f, ViewValueTerm)))
    if len(distinct) > 1:
        raise ValueError(f"a spec publishes two values: {distinct}")
    return distinct[0]
