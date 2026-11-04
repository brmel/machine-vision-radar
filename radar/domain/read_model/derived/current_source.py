from __future__ import annotations

from collections.abc import Iterable

from radar.domain.model.entities import Source
from radar.domain.model.registry import Registry

def _rank(source_type: str, registry: Registry) -> int:
    term = registry.vocabularies["source_types"].get(source_type)
    if term is None or term.preference is None:
        raise ValueError(f"source type '{source_type}' has no preference rank")
    return term.preference

def current_source(sources: Iterable[Source], registry: Registry) -> Source:
    return max(sorted(sources, key=lambda s: s.id), key=lambda s: (-_rank(s.type, registry), s.retrieved_at))
