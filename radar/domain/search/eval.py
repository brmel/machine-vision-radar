from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Mapping, Sequence

from radar.domain.model.entities import EvalQuery, WeekCounts, WeeklyCounts
from radar.domain.ports.search.ask_ledger import AskLedger
from radar.domain.ports.search.search_engine import Hit

@dataclass(frozen=True, slots=True)
class Outcome:
    query: EvalQuery
    rank: int | None
    returned: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class Score:
    outcomes: tuple[Outcome, ...]

    @property
    def hits(self) -> int:
        return sum(1 for o in self.outcomes if o.rank is not None)

    @property
    def hit_rate(self) -> float:
        return self.hits / len(self.outcomes) if self.outcomes else 0.0

    @property
    def mrr(self) -> float:
        return sum(1.0 / o.rank for o in self.outcomes if o.rank) / len(self.outcomes) if self.outcomes else 0.0

@dataclass(frozen=True, slots=True)
class Kpis:
    searches: int
    zero_results: int
    clicks: int
    answers: int
    refusals: int

    @classmethod
    def of(cls, counts: Mapping[str, int]) -> Kpis:
        return cls(counts.get("search", 0), counts.get("zero_result", 0), counts.get("result_click", 0),
                   counts.get("answer", 0), counts.get("refusal", 0))

    @staticmethod
    def _share(part: int, whole: int) -> float | None:
        return round(part / whole, 4) if whole else None

    def rates(self) -> dict[str, float | None]:
        return {"click_through": self._share(self.clicks, self.searches),
                "zero_result": self._share(self.zero_results, self.searches),
                "ask_refusal": self._share(self.refusals, self.answers + self.refusals)}

def _rank(query: EvalQuery, hits: Sequence[Hit]) -> int | None:
    good = (n for n, h in enumerate(hits, start=1) if h.card.id in query.targets or h.card.category == query.category)
    return next(good, None)

def evaluate(queries: Sequence[EvalQuery], search: Callable[[str, int], Sequence[Hit]], k: int = 5) -> Score:
    outcomes = []
    for q in sorted(queries, key=lambda q: q.id):
        hits = list(search(q.query, k))[:k]
        outcomes.append(Outcome(q, _rank(q, hits), tuple(h.card.id for h in hits)))
    return Score(tuple(outcomes))

@dataclass(frozen=True, slots=True)
class Period:
    first: date
    last: date
    counts: dict[str, int]
    kpis: dict[str, float | None]

@dataclass(frozen=True, slots=True)
class Traffic:
    ledger: AskLedger

    def _period(self, first: date, last: date) -> Period:
        totals: Counter[str] = Counter()
        for n in range((last - first).days + 1):
            totals.update(self.ledger.counted((first + timedelta(days=n)).isoformat()))
        return Period(first, last, dict(sorted(totals.items())), Kpis.of(totals).rates())

    def days(self, last: date, days: int) -> Period:
        return self._period(last - timedelta(days=days - 1), last)

    def weeks(self, last: date, weeks: int) -> WeeklyCounts:
        mondays = (last - timedelta(days=last.weekday(), weeks=n) for n in range(weeks))
        periods = (self._period(monday, min(monday + timedelta(days=6), last)) for monday in mondays)
        return WeeklyCounts(weeks=tuple(
            WeekCounts(week=p.first.isoformat(), to=p.last.isoformat(), counts=p.counts,
                       kpis={k: v for k, v in p.kpis.items() if v is not None}) for p in periods))
