from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Mapping, Sequence

from radar.domain.model.entities import EvalQuery, WeekCounts, WeeklyCounts
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

def weekly(counted: Callable[[str], Mapping[str, int]], last: date, weeks: int) -> WeeklyCounts:
    out = []
    for n in range(weeks):
        monday = last - timedelta(days=last.weekday(), weeks=n)
        days = [d for d in (monday + timedelta(days=i) for i in range(7)) if d <= last]
        totals: Counter[str] = Counter()
        for d in days:
            totals.update(counted(d.isoformat()))
        rates = {k: v for k, v in Kpis.of(totals).rates().items() if v is not None}
        out.append(WeekCounts(week=monday.isoformat(), to=days[-1].isoformat(), counts=dict(sorted(totals.items())),
                              kpis=rates))
    return WeeklyCounts(weeks=tuple(out))
