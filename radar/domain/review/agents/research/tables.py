from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from radar.domain.model.entities import ProductCard, SpecDefinition
from radar.domain.model.registry import Registry
from radar.domain.ports.web.reader import Page
from radar.domain.review.agents.drafts import Words, spelled

NUMBER = r"[-+]?\d[\d,]*(?:\.\d+)?"
BOUND = re.compile(r"[<>≤≥]|\bup to\b|\btbd\b|^see\b|\bmin(?:imum)?\b|\b(?:less|more|greater) than\b"
                   r"|\bat (?:least|most)\b|\bor (?:less|lower|more|higher)\b", re.I)
FOOTNOTE = re.compile(r"\(\d+\)|\*\d+")
UNIT_CELL = re.compile(r"\(([^()]+)\)")
FIGURE = re.compile(rf"({NUMBER})(?:\s*(?:to|–|-)\s*({NUMBER}))?\s*([^\d\s,;()]+)?")
TWO_DIMENSIONS = re.compile(r"\d\s*[x×*/]\s*\d")
LEADING_FIGURE = re.compile(rf"^(?:{NUMBER}(?:\s*(?:to|–|-)\s*{NUMBER})?)")
BETWEEN_TERMS = re.compile(r"[,;]|(?<!\d)/|/(?!\d)")
LABEL_MOST = 60
NOT_WORD = re.compile(r"[^\w.]+")
ANSWERS = {"yes": True, "no": False}
Value = dict[str, object]

@dataclass(frozen=True, slots=True)
class Table:
    claims: tuple[tuple[str, Value], ...]
    unmatched: tuple[str, ...]

def _rows(text: str) -> list[tuple[str, str]]:
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|") if c.strip() and not FOOTNOTE.fullmatch(c.strip())]
        if len(cells) == 2:
            rows.append((FOOTNOTE.sub("", cells[0]).strip(), cells[1]))
        elif len(cells) == 3 and (unit := UNIT_CELL.fullmatch(cells[1])):
            value = LEADING_FIGURE.sub(lambda m: f"{m.group(0)} {unit.group(1)}", cells[2], count=1)
            rows.append((FOOTNOTE.sub("", cells[0]).strip(), value))
    return rows

def _number(text: str) -> float:
    return float(text.replace(",", ""))

def _quantity(cell: str, said: Mapping[str, str]) -> Value | None:
    found = [m for m in FIGURE.finditer(FOOTNOTE.sub(" ", cell)) if m.group(3) and spelled(m.group(3)) in said]
    if len(found) != 1 or TWO_DIMENSIONS.search(cell):
        return None
    low, high, unit = found[0].groups()
    return ({"range": {"min": _number(low), "max": _number(high), "unit": said[spelled(unit)]}} if high
            else {"quantity": {"value": _number(low), "unit": said[spelled(unit)]}})

def _bounded(value: Value, spec: SpecDefinition, registry: Registry) -> bool:
    measure = value.get("quantity") or value.get("range")
    if not isinstance(measure, dict) or not spec.bounds or not spec.unit:
        return True
    ends = (measure["value"],) if "value" in measure else (measure["min"], measure["max"])
    converted = (registry.converted(end, measure["unit"], spec.unit) for end in ends)
    return all(spec.bounds.min <= end <= spec.bounds.max for end in converted)

def _terms(cell: str, spec: SpecDefinition, said: Mapping[str, str]) -> Value | None:
    whole = said.get(spelled(cell))
    parts = map(spelled, BETWEEN_TERMS.split(cell))
    named = [whole] if whole else list(dict.fromkeys(said[w] for w in parts if w in said))
    if spec.datatype == "term_set":
        return {"terms": named} if named else None
    return {"term": named[0]} if len(named) == 1 else None

def _value(label: str, cell: str, spec: SpecDefinition, said: Mapping[str, str]) -> Value | None:
    if BOUND.search(cell):
        return None
    match spec.datatype:
        case "quantity":
            return _quantity(cell, said)
        case "term" | "term_set":
            return _terms(cell, spec, said)
        case "boolean":
            return {"boolean": ANSWERS[cell.casefold()]} if cell.casefold() in ANSWERS else None
        case _:
            return {"string": cell} if len(cell) <= 60 and spelled(label) not in spelled(cell) else None

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
        labels, stated, unmatched = self._labels(card.category), {}, []
        for label, cell in _rows(page.text):
            key = labels.get(spelled(label))
            if key is None:
                unmatched += [label] if len(label) <= LABEL_MOST else []
                continue
            spec = self._registry.spec_definitions[key]
            value = _value(label, cell, spec, self._words[key])
            if value is not None and _bounded(value, spec, self._registry):
                stated.setdefault(key, []).append(value)
        return Table(tuple((k, v[0]) for k, v in stated.items() if all(o == v[0] for o in v)),
                     tuple(dict.fromkeys(unmatched)))

def _words_of(text: str) -> str:
    return f" {NOT_WORD.sub(' ', text.casefold()).strip()} "

def named_card(page: Page, cards: tuple[ProductCard, ...]) -> ProductCard | None:
    title = _words_of(page.title)
    named = sorted((c for c in cards if _words_of(c.name) in title), key=lambda c: len(c.name), reverse=True)
    return named[0] if named and (len(named) == 1 or len(named[0].name) > len(named[1].name)) else None
