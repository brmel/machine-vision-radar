from __future__ import annotations

import re

import pint
import pytest

from radar.adapters.files.json_parser import ModelParser, ParseError
from radar.tests.fixtures.corpus import REGISTRY, SCHEMA

UNITS = pint.UnitRegistry()

def _pint(ucum: str) -> pint.Quantity:
    code = (re.sub(r"\{[^}]*\}", "", ucum).replace("10*", "1e").replace("Cel", "degC").replace("By", "byte")
            .replace("%", "percent"))
    return (UNITS.Quantity(1, "dimensionless") if code in ("", "1")
            else UNITS(f"1{code}" if code.startswith("/") else code))

@pytest.mark.parametrize("unit", sorted(REGISTRY.units))
def test_a_units_factor_is_pints(unit: str) -> None:
    u = REGISTRY.units[unit]
    canonical = REGISTRY.units[REGISTRY.dimensions[u.dimension].canonical_unit]
    stated, base = _pint(u.ucum), _pint(canonical.ucum)
    assert stated.to(base.units).magnitude / base.magnitude == pytest.approx(u.factor, rel=1e-12)

@pytest.mark.parametrize("missing", ["ucum", "factor"])
def test_a_unit_without_its_code_or_factor_is_refused(missing: str) -> None:
    raw = {"id": "furlong", "symbol": "fur", "dimension": "length", "ucum": "[fur_us]", "factor": 201.168}
    with pytest.raises(ParseError, match=missing):
        ModelParser(SCHEMA).record({k: v for k, v in raw.items() if k != missing}, SCHEMA.types["Unit"], "units.json")
