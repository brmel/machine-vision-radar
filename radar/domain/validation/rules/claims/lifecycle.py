from __future__ import annotations

from radar.domain.model.entities import LifecycleEvent, Relation
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings

NAME = "lifecycle"

def check(ctx: ValidationContext) -> Findings:
    superseded = ctx.registry.marked("lifecycle_event_states", lambda t: t.superseded)
    naming = ctx.registry.marked("lifecycle_event_types", lambda t: t.names_successor)
    succeeding = ctx.registry.marked("relation_types", lambda t: t.succeeds)
    tied = {(r.from_entity, r.to_entity) for r in ctx.catalog.all(Relation) if r.type in succeeding}
    events = {(e.id, e.product, e.type) for e in ctx.catalog.all(LifecycleEvent)}
    for e in ctx.catalog.all(LifecycleEvent):
        if e.state in superseded and (e.revised_by, e.product, e.type) not in events:
            yield Finding(NAME, e.id, f"a {e.state} event names, in revised_by, the event of the same product and type "
                                      "that revises it")
        if (e.type in naming) != (e.successor is not None):
            yield Finding(NAME, e.id, f"successor is set on {', '.join(sorted(naming))} events, and only there")
        elif e.successor and (e.successor, e.product) not in tied:
            yield Finding(NAME, e.id, f"{e.successor} has no {', '.join(sorted(succeeding))} relation to {e.product}")
