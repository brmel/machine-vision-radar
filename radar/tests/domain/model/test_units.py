from __future__ import annotations

import re

import pint
import pytest

from radar.tests.fixtures.corpus import REGISTRY

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
