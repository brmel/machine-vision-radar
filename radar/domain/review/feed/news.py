from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from radar.domain.model.entities import FeedBrief, FeedItem, FeedPageView, SourceView, TermRef
from radar.domain.model.history.projection import plain
from radar.domain.model.registry import Registry
from radar.domain.ports.catalog.views import Check

Row = dict[str, Any]
KINDS = "feed_item_kinds"

@dataclass(frozen=True, slots=True)
class Cited:
    products: Mapping[str, Row]
    organizations: Mapping[str, Row]
    sources: Mapping[str, SourceView]

    def cite(self, ref: str) -> Row:
        if ref in self.products:
            return {"id": ref, "kind": "product", "label": self.products[ref]["name"],
                    "slug": self.products[ref]["slug"]}
        if ref in self.organizations:
            return {"id": ref, "kind": "organization", "label": self.organizations[ref]["name"],
                    "slug": self.organizations[ref]["slug"]}
        source = self.sources[ref]
        return {"id": ref, "kind": "source", "type": plain(source.type), **({"url": source.url} if source.url else {}),
                **({"label": source.title} if source.title else {})}

def published(items: Iterable[FeedItem]) -> list[FeedItem]:
    return sorted((i for i in items if i.published_at), key=lambda i: (i.published_at or "", i.id), reverse=True)

def _item_view(item: FeedItem, cited: Cited, registry: Registry) -> Row:
    kind = registry.vocabularies[KINDS][item.kind]
    return {"slug": item.slug, "kind": {"id": item.kind, "label": dict(kind.label)}, "authorship": item.authorship,
            "byline": dict(item.byline), "title": dict(item.title), "summary": dict(item.summary),
            "published_at": item.published_at, **({"revised_at": item.revised_at} if item.revised_at else {}),
            "body": [{"text": dict(s.text), "cites": [cited.cite(c) for c in s.cites]} for s in item.body],
            **({"event_date": plain(item.event_date), "event_source": plain(cited.sources[item.event_source])}
               if item.event_date and item.event_source else {})}

def _brief(view: Row, cited: Cited) -> FeedBrief:
    refs = [c["id"] for s in view["body"] for c in s["cites"] if c["kind"] != "source"]
    subjects = tuple(dict.fromkeys(refs))
    categories = tuple(dict.fromkeys(cited.products[r]["category"] for r in subjects if r in cited.products))
    return FeedBrief(slug=view["slug"], title=view["title"], summary=view["summary"], kind=TermRef(**view["kind"]),
                     published_at=view["published_at"], subjects=subjects, categories=categories)

def news(items: Iterable[FeedItem], cited: Cited, registry: Registry,
         checked: Check) -> tuple[dict[str, Row], FeedPageView]:
    views = {i.slug: checked(_item_view(i, cited, registry), "FeedItemView", i.slug) for i in published(items)}
    feed = FeedPageView(items=tuple(_brief(v, cited) for v in views.values()), total=len(views))
    checked(plain(feed), "FeedPageView", "news")
    return views, feed
