from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from radar.domain.model.history.projection import plain
from radar.domain.model.entities import (IndexView, ProductCard, ProductView, ViewValue, ViewValueBoolean,
                                         ViewValueQuantity, ViewValueNone, ViewValueRange, ViewValueString,
                                         ViewValueTerm, ViewValueTerms)
from radar.domain.model.registry import Registry
from radar.domain.read_model.facets import js_number
from radar.domain.read_model.listings import parse_card
from radar.domain.search.terms import terms

@dataclass(frozen=True, slots=True)
class Labels:
    categories: Mapping[str, Mapping[str, str]]
    aliases: Mapping[str, tuple[str, ...]]

    @classmethod
    def of(cls, index: IndexView, registry: Registry) -> Labels:
        return cls({c.id: c.label for c in index.categories},
                   {s.id: s.aliases for s in registry.spec_definitions.values() if s.aliases})

@dataclass(frozen=True, slots=True)
class Record:
    id: str
    slug: str
    name: str
    category: str
    card: ProductCard
    terms: Mapping[str, tuple[str, ...]]
    specs: Mapping[str, tuple[str, ...]]
    values: Mapping[str, ViewValue]

    def to_json(self) -> dict[str, Any]:
        return {"card": plain(self.card), "terms": {k: " ".join(v) for k, v in self.terms.items()},
                "specs": {k: " ".join(v) for k, v in self.specs.items()}, "values": plain(self.values)}

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Record:
        card = parse_card(raw["card"])
        return cls(card.id, card.slug, card.name, card.category, card,
                   {k: tuple(v.split()) for k, v in raw["terms"].items()},
                   {k: tuple(v.split()) for k, v in raw["specs"].items()}, raw.get("values") or {})

def value_words(value: ViewValue) -> list[str]:
    match value:
        case ViewValueTerm(term=t) | ViewValueNone(none=t):
            return [t.id, *t.label.values()]
        case ViewValueTerms(terms=ts):
            return [w for t in ts for w in (t.id, *t.label.values())]
        case ViewValueQuantity(quantity=q):
            return [js_number(q.value)]
        case ViewValueRange(range=r):
            return [js_number(r.min), js_number(r.max)]
        case ViewValueBoolean(boolean=b):
            return ["true" if b else "false"]
        case ViewValueString(string=text):
            return [text]
    return []

def published(view: ProductView) -> dict[str, ViewValue]:
    return {c.key: c.value for c in sorted((*view.core, *view.detail), key=lambda c: c.key) if c.value is not None}

def _all_languages(text: Mapping[str, str] | None) -> str:
    return " ".join(text.values()) if text else ""

def record_of(card: ProductCard, view: ProductView, labels: Labels) -> Record:
    values = published(view)
    fields = {
        "name": terms(" ".join([card.name, *(view.aliases or ())])),
        "vendor": terms(card.vendor_name),
        "category": terms(_all_languages(labels.categories.get(card.category))),
        "summary": terms(_all_languages(card.summary)),
    }
    return Record(card.id, card.slug, card.name, card.category, card,
                  {k: tuple(v) for k, v in fields.items()},
                  {k: tuple(terms(" ".join([*value_words(v), *labels.aliases.get(k, ())]))) for k, v in values.items()},
                  values)

def embedding_text(record: Record, view: ProductView, labels: Labels) -> str:
    cat_label = labels.categories.get(record.category, {})
    cat_text = next(iter(cat_label.values()), record.category)
    parts = [f"{record.name} by {record.card.vendor_name}.", cat_text + "."]
    if view.summary:
        parts += list(view.summary.values())
    specs = [f"{k}: {' '.join(value_words(v))}" for k, v in record.values.items()][:12]
    if specs:
        parts.append("Key specs: " + "; ".join(specs))
    return " ".join(parts)

def fingerprint(record: Record, text: str) -> str:
    blob = json.dumps({"record": record.to_json(), "text": text}, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
