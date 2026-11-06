from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from radar.domain.model.entities import (FeedBrief, FeedCite, FeedItem, FeedItemView, FeedPageView, FeedSentenceView,
                                         SourceView, TermRef)
from radar.domain.model.registry import Registry

Row = dict[str, Any]
KINDS = "feed_item_kinds"

@dataclass(frozen=True, slots=True)
class Cited:
    products: Mapping[str, Row]
    organizations: Mapping[str, Row]
    sources: Mapping[str, SourceView]

    def cite(self, ref: str) -> FeedCite:
        if ref in self.products:
            return FeedCite(id=ref, kind="product", label=self.products[ref]["name"], slug=self.products[ref]["slug"])
        if ref in self.organizations:
            row = self.organizations[ref]
            return FeedCite(id=ref, kind="organization", label=row["name"], slug=row["slug"])
        source = self.sources[ref]
        return FeedCite(id=ref, kind="source", type=source.type, url=source.url, label=source.title)

def published(items: Iterable[FeedItem]) -> list[FeedItem]:
    return sorted((i for i in items if i.published_at), key=lambda i: (i.published_at or "", i.id), reverse=True)

def _item_view(item: FeedItem, cited: Cited, registry: Registry) -> FeedItemView:
    kind = registry.vocabularies[KINDS][item.kind]
    dated = bool(item.event_date and item.event_source)
    return FeedItemView(slug=item.slug, kind=TermRef(id=item.kind, label=dict(kind.label)), authorship=item.authorship,
                        byline=dict(item.byline), title=dict(item.title), summary=dict(item.summary),
                        body=tuple(FeedSentenceView(text=dict(s.text), cites=tuple(cited.cite(c) for c in s.cites))
                                   for s in item.body),
                        published_at=item.published_at or "", revised_at=item.revised_at or None,
                        event_date=item.event_date if dated else None,
                        event_source=cited.sources[item.event_source] if dated and item.event_source else None)

def _brief(view: FeedItemView, cited: Cited) -> FeedBrief:
    refs = [c.id for s in view.body for c in s.cites if c.kind != "source"]
    subjects = tuple(dict.fromkeys(refs))
    categories = tuple(dict.fromkeys(cited.products[r]["category"] for r in subjects if r in cited.products))
    return FeedBrief(slug=view.slug, title=view.title, summary=view.summary, kind=view.kind,
                     published_at=view.published_at, subjects=subjects, categories=categories)

def news(items: Iterable[FeedItem], cited: Cited, registry: Registry) -> tuple[dict[str, FeedItemView], FeedPageView]:
    views = {i.slug: _item_view(i, cited, registry) for i in published(items)}
    return views, FeedPageView(items=tuple(_brief(v, cited) for v in views.values()), total=len(views))
