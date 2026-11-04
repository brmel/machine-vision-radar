from __future__ import annotations

from radar.domain.model.entities import FeedItem
from radar.domain.validation.context import ValidationContext, ValidationResult

NAME = "feed_review"

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    byline = dict(ctx.registry.feed.byline)
    for item in ctx.catalog.all(FeedItem):
        if dict(item.byline) != byline:
            res.error(NAME, item.id, f"the byline is the brand's, {byline}, not {dict(item.byline)}")
