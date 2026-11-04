from __future__ import annotations

from typing import Callable

from radar.domain.model.entities import IndexRunView, IndexSettings, IndexStatus, SearchSettings
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.search.index_runs import Action, IndexRuns
from radar.domain.ports.search.search_engine import Built, NoIndex, SearchEngine

RUNS = 10

class Indexer:
    def __init__(self, engine: SearchEngine, read_model: CatalogRepository, runs: IndexRuns, search: SearchSettings,
                 clock: Callable[[], str]) -> None:
        self._engine, self._read_model, self._runs, self._search, self._clock = engine, read_model, runs, search, clock

    def run(self, action: Action, actor: str, correlation_id: str) -> Built:
        at = self._clock()
        try:
            built = self._engine.index(action)
        except Exception as exc:
            self._runs.record(IndexRunView(action=action, model_id=self._search.model, actor=actor, at=at,
                                           correlation_id=correlation_id, products=0, embedded=0, removed=0,
                                           error=str(exc)))
            raise
        self._runs.record(IndexRunView(action=action, model_id=self._search.model, actor=actor, at=at,
                                       correlation_id=correlation_id, version=built.version, products=built.products,
                                       embedded=len(built.embedded), removed=len(built.removed)))
        return built

    def status(self) -> IndexStatus:
        runs = tuple(self._runs.latest(RUNS))
        catalog = len(self._read_model.index().products)
        try:
            current = self._engine.last_indexed()
        except NoIndex:
            return IndexStatus(products_in_catalog=catalog, runs=runs)
        return IndexStatus(products_in_catalog=catalog, runs=runs, version=current.version, embedder=current.model,
                           products_indexed=current.products,
                           built_at=next((r.at for r in reversed(runs) if r.version == current.version), None))

    def settings(self) -> IndexSettings:
        return IndexSettings(search=self._search, current=self.status().embedder)
