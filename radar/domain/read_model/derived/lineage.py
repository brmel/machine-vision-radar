from __future__ import annotations

from dataclasses import dataclass

from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import LifecycleEvent, ObservedStatus
from radar.domain.model.registry import Registry

@dataclass(frozen=True, slots=True)
class DisplayedStatus:
    term: str
    source_refs: tuple[str, ...]

    @staticmethod
    def of(catalog: Catalog, registry: Registry, product: str) -> DisplayedStatus | None:
        types, states = registry.vocabularies["lifecycle_event_types"], registry.vocabularies["lifecycle_event_states"]
        events = sorted((e for e in catalog.all(LifecycleEvent) if e.product == product and states[e.state].occurred
                         and types[e.type].sets_status),
                        key=lambda e: e.date.value)
        if events:
            return DisplayedStatus(events[-1].type, events[-1].source_refs)
        observed = next((o for o in catalog.all(ObservedStatus) if o.product == product), None)
        return DisplayedStatus(observed.status, observed.source_refs) if observed else None
