from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from radar.domain.model.entities import ProductCard, SpecDefinition
from radar.domain.model.registry import Registry
from radar.domain.ports.web.reader import Page
from radar.domain.review.agents.drafts import Words, spelled

NUMBER = r"[-+]?\d[\d,]*(?:\.\d+)?"
BOUND = re.compile(r"[<>≤≥]|\bup to\b|\btbd\b|^see\b|\bmin(?:imum)?\b", re.I)
FOOTNOTE = re.compile(r"\(\d+\)|\*\d+")
UNIT_CELL = re.compile(r"\(([^()]+)\)")
FIGURE = re.compile(rf"({NUMBER})(?:\s*(?:to|–|-)\s*({NUMBER}))?\s*([^\d\s,;()]+)?")
ANSWERS = {"yes": True, "no": False}
Value = dict[str, object]

@dataclass(frozen=True, slots=True)
class Table:
    claims: tuple[tuple[str, Value], ...]
    unmatched: tuple[str, ...]

def _rows(text: str) -> list[tuple[str, str]]:
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.split(" | ") if not FOOTNOTE.fullmatch(c.strip())]
        if len(cells) == 2:
            rows.append((cells[0], cells[1]))
        elif len(cells) == 3 and (unit := UNIT_CELL.fullmatch(cells[1])):
            rows.append((cells[0], f"{cells[2]} {unit.group(1)}"))
    return rows

def _number(text: str) -> float:
    return float(text.replace(",", ""))

def _quantity(cell: str, spec: SpecDefinition, said: Mapping[str, str]) -> Value | None:
    found = [m for m in FIGURE.finditer(FOOTNOTE.sub(" ", cell)) if m.group(3) and spelled(m.group(3)) in said]
    if len(found) != 1:
        return None
    low, high, unit = found[0].groups()
    value: Value = ({"range": {"min": _number(low), "max": _number(high), "unit": said[spelled(unit)]}} if high
                    else {"quantity": {"value": _number(low), "unit": said[spelled(unit)]}})
    return value if _within(spec, unit == spec.unit, _number(low), _number(high or low)) else None

def _within(spec: SpecDefinition, own_unit: bool, low: float, high: float) -> bool:
    return not (own_unit and spec.bounds) or spec.bounds.min <= low <= high <= spec.bounds.max

def _terms(cell: str, spec: SpecDefinition, said: Mapping[str, str]) -> Value | None:
    named = list(dict.fromkeys(said[w] for w in map(spelled, re.split(r"[,;/]", cell)) if w in said))
    if spec.datatype == "term_set":
        return {"terms": named} if named else None
    return {"term": named[0]} if len(named) == 1 else None

def _value(cell: str, spec: SpecDefinition, said: Mapping[str, str]) -> Value | None:
    if BOUND.search(cell):
        return None
    match spec.datatype:
        case "quantity":
            return _quantity(cell, spec, said)
        case "term" | "term_set":
            return _terms(cell, spec, said)
        case "boolean":
            return {"boolean": ANSWERS[cell.casefold()]} if cell.casefold() in ANSWERS else None
        case _:
            return {"string": cell} if len(cell) <= 60 else None

class Tables:
    def __init__(self, registry: Registry, words: Words) -> None:
        self._registry, self._words = registry, words

    def _labels(self, category: str) -> dict[str, str | None]:
        sections = self._registry.profile(category).sections
        labels: dict[str, str | None] = {}
        for key in (*sections.core, *sections.detail):
            spec = self._registry.spec_definitions[key]
            for said in {spelled(w) for w in (key, *spec.label.values(), *(spec.aliases or ()))}:
                labels[said] = None if said in labels else key
        return labels

    def read(self, page: Page, card: ProductCard) -> Table:
        labels, claims, unmatched = self._labels(card.category), {}, []
        for label, cell in _rows(page.text):
            key = labels.get(spelled(label))
            if key is None:
                unmatched.append(label)
                continue
            value = _value(cell, self._registry.spec_definitions[key], self._words[key])
            if value is not None and key not in claims:
                claims[key] = value
        return Table(tuple(claims.items()), tuple(dict.fromkeys(unmatched)))

def named_card(page: Page, cards: tuple[ProductCard, ...]) -> ProductCard | None:
    title = spelled(page.title)
    named = sorted((c for c in cards if spelled(c.name) in title), key=lambda c: len(c.name), reverse=True)
    return named[0] if named and (len(named) == 1 or len(named[0].name) > len(named[1].name)) else None
