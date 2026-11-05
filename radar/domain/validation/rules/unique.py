from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from radar.domain.validation.context import ValidationContext, Whole
from radar.domain.validation.verdict import Finding, Findings, Severity
from radar.domain.validation.walk import visits

NAME = "unique"

def check(ctx: ValidationContext) -> Findings:
    severity = Severity.WARNING if isinstance(ctx.scope, Whole) else Severity.ERROR
    holders: defaultdict[tuple[str, object], list[str]] = defaultdict(list)
    for v in visits(ctx):
        if v.spec.unique and v.value != "":
            holders[v.path, v.value].append(v.entity.id)
    for (path, value), ids in holders.items():
        for first, second in combinations(sorted(ids), 2):
            yield Finding(NAME, second, f"{path} '{value}' is held by {first} and {second}", severity)
