from __future__ import annotations

import re

from radar.domain.model.entities import FeedItem
from radar.domain.validation.context import ValidationContext, ValidationResult

NAME = "feed"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    byline = dict(ctx.registry.feed.byline)
    for item in ctx.catalog.all(FeedItem):
        cited = {c for s in item.body for c in s.cites}
        for broken, message in (
                (set(item.cites) != cited,
                 f"cites {sorted(item.cites)} is not what its sentences cite, {sorted(cited)}"),
                (bool(item.event_source) and item.event_source not in cited,
                 f"event_source {item.event_source} is not cited by any sentence"),
                ((item.event_date is None) != (item.event_source is None),
                 "event_date and event_source come together: a vendor's date only with its source"),
                (bool(item.revised_at) and not item.published_at,
                 "revised_at comes only with published_at: a draft is edited, not revised"),
                (dict(item.byline) != byline, f"the byline is the brand's, {byline}, not {dict(item.byline)}"),
                (not SLUG.fullmatch(item.slug), f"slug '{item.slug}' is lowercase words joined by hyphens")):
            if broken:
                res.error(NAME, item.id, message)
