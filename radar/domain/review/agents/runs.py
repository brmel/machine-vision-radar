from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from radar.domain.model.entities import (CategoryCells, Claim, Product, ProposalStatus, ResearchLine, ResearchMeasures,
                                         ResearchRunList, ResearchRunRow, ResearchRunView)
from radar.domain.model.history.projection import every_page
from radar.domain.model.model import Model
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.catalog.held_records import HeldRecords
from radar.domain.ports.review.proposal_queue import Query
from radar.domain.ports.review.proposing import Proposing
from radar.domain.ports.review.research_runs import LABELS, ResearchRun, ResearchRunLog, RunPage, Status, Step
from radar.domain.review.bundle import puts
from radar.domain.review.proposal import Proposal
from radar.domain.review.requests import Founder

def _status(run: ResearchRun) -> str:
    return (run.outcome.status if run.outcome else Status.RUNNING).value

def run_view(run: ResearchRun) -> ResearchRunView:
    return ResearchRunView(id=run.id, scope=run.scope, actor=run.actor, started_at=run.started_at,
                           ended_at=run.outcome.at if run.outcome else None, status=_status(run), token=run.token,
                           cad=round(run.cad, 6), pages=run.said(Step.READ),
                           filed=run.said(Step.FILED, Step.MEDIA, Step.DATASHEET), media=run.said(Step.MEDIA),
                           datasheets=run.said(Step.DATASHEET), rejected=run.said(Step.REJECTED),
                           lines=tuple(ResearchLine(at=line.at, step=line.step.value, detail=line.detail)
                                       for line in run.lines))

def run_row(run: ResearchRun) -> ResearchRunRow:
    return ResearchRunRow(id=run.id, scope=run.scope, actor=run.actor, started_at=run.started_at,
                          ended_at=run.outcome.at if run.outcome else None, status=_status(run), cad=round(run.cad, 6),
                          pages=len(run.said(Step.READ)), filed=len(run.said(Step.FILED, Step.MEDIA, Step.DATASHEET)),
                          rejected=len(run.said(Step.REJECTED)))

def runs_view(page: RunPage) -> ResearchRunList:
    return ResearchRunList(runs=tuple(run_row(r) for r in page.runs), next=page.cursor, total=page.total)

def _started(runs: ResearchRunLog, instant: str) -> list[ResearchRun]:
    return [run for page in every_page(runs.page) for run in page.runs if run.started_at >= instant]

def _whys(runs: Sequence[ResearchRun], step: Step) -> Mapping[str, int]:
    return MappingProxyType(
        dict(Counter(detail.split(": ", 1)[-1] for run in runs for detail in run.said(step)).most_common()))

def _by_category(claims: Sequence[Claim], categories: Mapping[str, str]) -> Counter[str]:
    return Counter(categories[s] for s, _ in {(c.subject, c.spec_key) for c in claims})

@dataclass(frozen=True, slots=True)
class _Value:
    subject: str
    spec_key: str
    sources: frozenset[str]
    status: ProposalStatus
    is_filter: bool

def _labels(runs: Sequence[ResearchRun]) -> Mapping[str, int]:
    said = (label for run in runs for line in run.said(Step.UNMATCHED)
            for label in line.split(": ", 1)[1].split(LABELS))
    return MappingProxyType(dict(Counter(said).most_common()))

class Measure:
    def __init__(self, runs: ResearchRunLog, review: Proposing, read: CatalogRepository, held: HeldRecords,
                 model: Model) -> None:
        self._runs, self._review, self._read, self._held = runs, review, read, held
        profiles = model.registry.profiles
        self._filters = {p.category_id: frozenset(f.field for f in p.facets) for p in profiles}
        self._shown = {p.category_id: frozenset((*p.sections.core, *p.sections.detail)) for p in profiles}

    def since(self, instant: str, by: Founder) -> ResearchMeasures:
        runs, categories = _started(self._runs, instant), {card.id: card.category
                                                           for card in self._read.index().products}
        filed = [proposal for run in runs for proposal in run.said(Step.FILED, Step.MEDIA, Step.DATASHEET)]
        values = [value for proposal in self._bundled(runs, by) for value in self._values(proposal, categories)]
        return ResearchMeasures(since=instant, runs=len(runs), pages=sum(len(run.said(Step.READ)) for run in runs),
                                skipped=_whys(runs, Step.SKIPPED), labels=_labels(runs), filed=len(filed),
                                refused=_whys(runs, Step.REJECTED),
                                values=len(values), filter_values=sum(v.is_filter for v in values),
                                statuses=MappingProxyType(dict(Counter(v.status.value for v in values))),
                                published=self._published(values), cells=self._cells(instant, categories),
                                cad=round(sum(run.cad for run in runs), 6))

    def _bundled(self, runs: Sequence[ResearchRun], by: Founder) -> list[Proposal]:
        return [p for run in runs
                for page in every_page(lambda cursor: self._review.queue(Query(bundle=run.id), by, cursor))
                for p in page.proposals]

    def _values(self, proposal: Proposal, categories: Mapping[str, str]) -> list[_Value]:
        entities = [put.entity for put in puts(proposal)]
        made = {e.id: e.category for e in entities if isinstance(e, Product)}
        return [_Value(e.subject, e.spec_key, frozenset(e.source_refs), proposal.status,
                       e.spec_key in self._filters.get(made.get(e.subject) or categories.get(e.subject, ""), ()))
                for e in entities if isinstance(e, Claim)]

    def _published(self, values: Sequence[_Value]) -> int:
        approved = [v for v in values if v.status is ProposalStatus.APPROVED]
        pages = {subject: self._read.product(subject) for subject in {v.subject for v in approved}}
        return sum(any(c.key == v.spec_key and c.value is not None and c.source in v.sources
                       for c in (*page.core, *page.detail))
                   for v in approved if (page := pages[v.subject]))

    def _cells(self, instant: str, categories: Mapping[str, str]) -> Mapping[str, CategoryCells]:
        created = self._held.created_since(instant)
        claims = [c for c in self._held.claims() if c.applies_to_versions is None
                  and c.spec_key in self._shown.get(categories.get(c.subject, ""), ())]
        now, then = (_by_category(claims, categories),
                     _by_category([c for c in claims if c.id not in created], categories))
        return MappingProxyType({cid: CategoryCells(cells=n * len(self._shown[cid]), before=then[cid], now=now[cid])
                                 for cid, n in sorted(Counter(categories.values()).items()) if cid in self._shown})
