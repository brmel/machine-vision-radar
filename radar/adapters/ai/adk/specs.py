from __future__ import annotations

import json
from typing import Collection

from radar.adapters.files.model_json import DEFAULT_LANGUAGE
from radar.domain.model.entities import SpecDefinition
from radar.domain.model.registry import Registry

def _measure(spec: SpecDefinition, registry: Registry) -> dict[str, object]:
    units = sorted((u for u in registry.units.values() if u.dimension == spec.dimension),
                   key=lambda u: u.id != spec.unit)
    bounds = {"bounds": {"min": spec.bounds.min, "max": spec.bounds.max, "unit": spec.unit}} if spec.bounds else {}
    return {"units": {u.id: u.symbol for u in units}, **bounds}

def _terms(spec: SpecDefinition, registry: Registry) -> dict[str, object]:
    return {"terms": {t.id: t.label.get(DEFAULT_LANGUAGE.code, "")
                      for t in registry.vocabularies[spec.vocabulary].values()}} if spec.vocabulary else {}

def specs_json(registry: Registry, keys: Collection[str]) -> str:
    return json.dumps([{"id": s.id, "label": s.label.get(DEFAULT_LANGUAGE.code, ""), "datatype": s.datatype,
                        **({"aliases": list(s.aliases)} if s.aliases else {}),
                        **(_measure(s, registry) if s.datatype == "quantity" else _terms(s, registry))}
                       for s in registry.spec_definitions.values() if s.id in keys], ensure_ascii=False)
