from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from radar.domain.validation.context import ValidationContext, ValidationResult
from radar.domain.validation.walk import visits

NAME = "unique"

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    report = res.warn if ctx.whole_catalog else res.error
    holders: defaultdict[tuple[str, object], list[str]] = defaultdict(list)
    for v in visits(ctx):
        if v.spec.unique and v.value != "":
            holders[v.path, v.value].append(v.entity.id)
    for (path, value), ids in holders.items():
        for first, second in combinations(sorted(ids), 2):
            report(NAME, second, f"{path} '{value}' is held by {first} and {second}")
