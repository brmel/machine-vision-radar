from __future__ import annotations

import re

from radar.domain.model.entities import FeedItem
from radar.domain.validation.context import ValidationContext, ValidationResult

NAME = "feed_slugs"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    for item in ctx.catalog.all(FeedItem):
        if not SLUG.fullmatch(item.slug):
            res.error(NAME, item.id, f"slug '{item.slug}' is lowercase words joined by hyphens")
