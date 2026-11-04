from __future__ import annotations

from typing import Any, Callable, Collection, Iterable, Mapping, Sequence

from radar.domain.model.history.projection import every_page, json_text, states
from radar.domain.ports.history.version_store import EntityVersion, FieldChange, VersionStore
from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.schema import ModelSchema, TypeSpec
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.model.entities import (Change, FieldChangeView, FieldDiff, HistoryEntry, HistoryPage, HistoryView,
                                         Product, Source, SourceView)

def _changes(changed: Iterable[FieldChange]) -> tuple[FieldChangeView, ...]:
    return tuple(FieldChangeView(path=c.path, before=json_text(c.before), after=json_text(c.after)) for c in changed)

def _entry(v: EntityVersion, catalog: Catalog, source_view: Callable[[Source], SourceView],
           spec: str | None = None) -> HistoryEntry:
    return HistoryEntry(entity=v.entity, spec=spec, version=v.version, recorded_at=v.recorded_at,
                        actor_kind=v.actor_kind, actor=v.actor, reason=v.reason, changed=_changes(v.changed),
                        sources=tuple(source_view(s) for s in map(catalog.get, v.source_refs) if isinstance(s, Source)),
                        proposal=v.proposal, correlation_id=v.correlation_id)

def _versions(store: VersionStore, entity: str) -> list[EntityVersion]:
    return [v for page in every_page(lambda cursor: store.history(entity, cursor)) for v in page.versions]

class Histories:
    def __init__(self, versions: VersionStore, read: CatalogRepository, records: Callable[[Collection[str]], Catalog],
                 source_view: Callable[[Source], SourceView]) -> None:
        self._versions, self._read, self._records, self._source_view = versions, read, records, source_view

    def page(self, entity: str, cursor: str | None = None) -> HistoryPage:
        page = self._versions.history(entity, cursor)
        catalog = self._records({s for v in page.versions for s in v.source_refs})
        return HistoryPage(entity=entity, versions=tuple(_entry(v, catalog, self._source_view) for v in page.versions),
                           next=page.cursor, total=page.total)

    def diff(self, entity: str, v1: int, v2: int) -> FieldDiff:
        return FieldDiff(changes=_changes(self._versions.diff(entity, v1, v2)))

    def shown(self, entity: str, cursor: str | None = None) -> HistoryView | HistoryPage:
        return self._read.history(entity) or self.page(entity, cursor)

def _named(kind: TypeSpec, product: str, seen: Sequence[Mapping[str, Any]]) -> set[str]:
    refs = [f.name for f in kind.fields if product in f.refs]
    return {p for s in seen for f in refs for p in (s[f] if isinstance(s.get(f), list) else [s.get(f)]) if p}

def _spec(kind: TypeSpec, seen: Sequence[Mapping[str, Any]]) -> str | None:
    field = next((f.name for f in kind.fields if f.vocabulary == "spec_definitions"), None)
    return next((s[field] for s in reversed(seen) if field in s), None) if field else None

def listed(schema: ModelSchema, changes: Iterable[Change]) -> dict[str, dict[str, str | None]]:
    product = schema.types[Product.__name__]
    by_entity: dict[str, list[Change]] = {}
    for c in changes:
        by_entity.setdefault(c.entity, []).append(c)
    out: dict[str, dict[str, str | None]] = {}
    for entity, own in by_entity.items():
        kind_name = schema.kind_of(entity)
        if not kind_name:
            continue
        kind = schema.types[kind_name]
        if len(own) < 2 or kind.internal:
            continue
        if kind.name == product.name:
            out.setdefault(entity, {})[entity] = None
            continue
        seen = states(own)[1:]
        for p in _named(kind, product.name, seen):
            out.setdefault(p, {})[entity] = _spec(kind, seen)
    return out

def product_history(store: VersionStore, product: str, records: Mapping[str, str | None], catalog: Catalog,
                    source_view: Callable[[Source], SourceView]) -> HistoryView:
    entries = [_entry(v, catalog, source_view, spec) for e, spec in records.items() for v in _versions(store, e)]
    return HistoryView(entity=product,
                       versions=tuple(sorted(entries, key=lambda e: (e.recorded_at, e.entity, e.version),
                                             reverse=True)))
