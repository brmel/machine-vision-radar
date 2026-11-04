from __future__ import annotations

from radar.domain.model.entities import FeedItem
from radar.domain.validation.context import ValidationContext, ValidationResult

NAME = "feed_dates"

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    for item in ctx.catalog.all(FeedItem):
        if (item.event_date is None) != (item.event_source is None):
            res.error(NAME, item.id, "event_date and event_source come together: a vendor's date only with its source")
        if item.revised_at and not item.published_at:
            res.error(NAME, item.id, "revised_at comes only with published_at: a draft is edited, not revised")
