from __future__ import annotations

from radar.domain.model.entities import FeedItem
from radar.domain.validation.context import ValidationContext, ValidationResult

NAME = "feed_sources"

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    for item in ctx.catalog.all(FeedItem):
        cited = {c for s in item.body for c in s.cites}
        if set(item.cites) != cited:
            res.error(NAME, item.id, f"cites {sorted(item.cites)} is not what its sentences cite, {sorted(cited)}")
        if item.event_source and item.event_source not in cited:
            res.error(NAME, item.id, f"event_source {item.event_source} is not cited by any sentence")
