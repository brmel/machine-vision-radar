from __future__ import annotations

from datetime import datetime

from radar.domain.model.dates import start_of
from radar.domain.model.entities import LifecycleEvent, Source
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings, Severity
from radar.domain.validation.walk import Visit, visits

NAME = "dates"

def _expected_date(v: Visit, expected: frozenset[str]) -> bool:
    return isinstance(v.entity, LifecycleEvent) and v.entity.state in expected and v.path.endswith(".date")

def _announced(ctx: ValidationContext, event: LifecycleEvent) -> bool:
    sources = [ctx.catalog.get(ref) for ref in event.source_refs]
    return any(isinstance(s, Source) and s.published_at is not None for s in sources)

def check(ctx: ValidationContext) -> Findings:
    expected = ctx.registry.marked("lifecycle_event_states", lambda t: t.expected)
    for v in visits(ctx):
        if v.spec.leaf_type == "PartialDate":
            try:
                when = start_of(v.value)
            except ValueError as exc:
                yield Finding(NAME, v.entity.id, f"{v.path}: {exc}")
                continue
        elif v.spec.leaf_type == "Instant":
            when = datetime.fromisoformat(v.value.replace("Z", "+00:00")).date()
        else:
            continue
        if _expected_date(v, expected):
            if when <= ctx.today:
                yield Finding(NAME, v.entity.id, f"{v.path}: the expected date {v.value.value} has passed; revise it",
                              Severity.WARNING)
            elif not _announced(ctx, v.entity):
                yield Finding(NAME, v.entity.id, f"{v.path}: an expected event needs a cited source with published_at")
        elif when > ctx.today and not v.spec.future_allowed:
            yield Finding(NAME, v.entity.id, f"{v.path}: {when.isoformat()} is in the future")
