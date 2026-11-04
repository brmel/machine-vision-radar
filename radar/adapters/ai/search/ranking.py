from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from radar.domain.model.entities import SearchSettings
from radar.adapters.ai.search.records import Record
from radar.domain.ports.search.search_engine import Hit, Match
from radar.domain.search.terms import query_terms, words

@dataclass(frozen=True, slots=True)
class _Found:
    weight: float
    match: Match
    tokens: Sequence[str]
    at: Mapping[str, tuple[int, ...]]

def _groups(record: Record, name: str) -> Iterable[tuple[str | None, Sequence[str]]]:
    return record.specs.items() if name == "specs" else [(None, record.terms.get(name, ()))]

def _found(record: Record, query: Sequence[str], config: SearchSettings) -> list[_Found]:
    out = []
    for weighted in config.fields:
        for key, tokens in _groups(record, weighted.field):
            at = {q: tuple(i for i, t in enumerate(tokens) if t.startswith(q)) for q in query}
            found = tuple(q for q in query if at[q])
            if found:
                out.append(_Found(weighted.weight, Match(weighted.field, found, key), tokens, at))
    return out

def _near(a: Sequence[int], b: Sequence[int], window: int) -> bool:
    return any(abs(i - j) <= window for i in a for j in b)

def _score(found: Sequence[_Found], query: Sequence[str], rarity: Mapping[str, float], config: SearchSettings) -> float:
    score = 0.0
    for f in found:
        for q in f.match.terms:
            score += f.weight * rarity[q] * (config.whole_word if q in f.tokens else 1.0)
        for a, b in zip(query, query[1:]):
            if f.at[a] and f.at[b] and _near(f.at[a], f.at[b], config.pair_window):
                score += f.weight * config.pair_boost * (rarity[a] + rarity[b])
    return score

def _is_exact(record: Record, exact: str) -> bool:
    return bool(exact) and exact in (" ".join(words(record.id)), " ".join(words(record.slug)),
                                     " ".join(words(record.name)))

def _rarity(terms: Sequence[str], candidates: Sequence[Record],
            found: Mapping[str, Sequence[_Found]]) -> dict[str, float]:
    df = {q: sum(1 for r in candidates if any(q in f.match.terms for f in found[r.id])) for q in terms}
    return {q: math.sqrt(len(candidates) / n) if n else 0.0 for q, n in df.items()}

def keyword(records: Iterable[Record], query: str, config: SearchSettings) -> list[Hit]:
    terms, exact = query_terms(query, config), " ".join(words(query))
    candidates = list(records)
    found = {r.id: _found(r, terms, config) for r in candidates}
    rarity = _rarity(terms, candidates, found)
    hits = []
    for r in candidates:
        exact_hit = _is_exact(r, exact)
        if found[r.id] or exact_hit:
            score = _score(found[r.id], terms, rarity, config) + (config.exact_boost if exact_hit else 0.0)
            hits.append(Hit(r.card, score, tuple(f.match for f in found[r.id])))
    best = max((h.score for h in hits), default=0.0)
    return sorted((h for h in hits if h.score >= config.relative_cut * best), key=lambda h: (-h.score, h.card.id))

def semantic(records: Iterable[Record], vectors: Mapping[str, Sequence[float]], query: Sequence[float],
             threshold: float) -> list[Hit]:
    hits = [Hit(r.card, sim) for r in records if (sim := sum(a * b for a, b in zip(query, vectors[r.id]))) >= threshold]
    return sorted(hits, key=lambda h: (-h.score, h.card.id))

def blend(keyword_hits: Sequence[Hit], semantic_hits: Sequence[Hit], k: int) -> list[Hit]:
    by_id: dict[str, Hit] = {}
    fused: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for label, hits in (("keyword", keyword_hits), ("semantic", semantic_hits)):
        for rank, hit in enumerate(hits, start=1):
            pid = hit.card.id
            by_id.setdefault(pid, hit)
            ranks.setdefault(pid, {})[label] = rank
            fused[pid] = fused.get(pid, 0.0) + 1.0 / (k + rank)
    ordered = sorted(fused, key=lambda pid: (-fused[pid], pid))
    return [Hit(by_id[pid].card, fused[pid], by_id[pid].why, ranks[pid]) for pid in ordered]
