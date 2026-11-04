from __future__ import annotations

import re
from datetime import date

from radar.domain.model.entities import PartialDate

_FORMATS = {
    "year": r"(\d{4})",
    "half": r"(\d{4})-H([12])",
    "quarter": r"(\d{4})-Q([1-4])",
    "month": r"(\d{4})-(\d{2})",
    "day": r"(\d{4})-(\d{2})-(\d{2})",
}
_MONTHS_PER_PART = {"half": 6, "quarter": 3}

def start_of(d: PartialDate) -> date:
    m = re.fullmatch(_FORMATS[d.precision], d.value)
    if not m:
        raise ValueError(f"'{d.value}' is not a {d.precision}-precision date")
    year, *rest = (int(g) for g in m.groups())
    if d.precision in _MONTHS_PER_PART:
        return date(year, 1 + _MONTHS_PER_PART[d.precision] * (rest[0] - 1), 1)
    return date(year, *(rest + [1] * (2 - len(rest))))
