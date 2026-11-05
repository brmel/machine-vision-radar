from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, Iterable, Mapping, Sequence

from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import (FeedItem, FeedPageView, ModelRow, Organization, OrgRelation, Product,
                                         ProductView, Source)
from radar.domain.model.history.projection import Projection, plain
from radar.domain.model.registry import Registry
from radar.domain.model.schema import ModelSchema
from radar.domain.ports.catalog.views import Check, MediaUrl
from radar.domain.ports.history.change_log import ChangeLog
from radar.domain.read_model.derived.market import market
from radar.domain.read_model.derived.ownership import OwnershipHistory
from .history import listed, product_history
from .listings import Tally, index, index_card, listing_card, paginate
from .organizations import brief, organization_view
from .products.views import ProductViews
from radar.domain.review.feed.news import Cited, news
from radar.domain.read_model.derived.identity import identities

View = dict[str, Any]

@dataclass(frozen=True, slots=True)
class ReadModel:
    index: View
    products: dict[str, ProductView]
    pages: dict[str, list[View]]
    organizations: dict[str, View]
    histories: dict[str, View]
    tally: Tally
    news: dict[str, View]
    feed: FeedPageView
    market: View

    @property
    def registry(self) -> View:
        return {k: v for k, v in self.index.items() if k not in ("products", "organizations")}

def product_views(catalog: Catalog, registry: Registry, schema: ModelSchema, checked: Check, media_url: MediaUrl,
                  revised: Collection[str], ids: Iterable[str] | None = None,
                  kept: Mapping[str, Sequence[ModelRow]] | None = None) -> tuple[ProductViews, dict[str, ProductView]]:
    orgs = {o.id: o for o in catalog.all(Organization)}
    products = {p.id: p for p in catalog.all(Product)}
    wanted = sorted(products if ids is None else ids)
    names, makers = identities(catalog, registry)
    missing = [pid for pid in wanted if pid not in makers or pid not in names]
    if missing:
        raise ValueError(f"product {missing[0]} has no vendor role or no primary name")
    builder = ProductViews(catalog, registry, schema, products, media_url, wanted, kept)
    views = {pid: builder.view(products[pid], names, brief(orgs[makers[pid]]), pid in revised) for pid in wanted}
    for pid, view in views.items():
        checked(plain(view), "ProductView", pid)
    return builder, views

def thin(catalog: Catalog, registry: Registry, schema: ModelSchema, checked: Check, media_url: MediaUrl) -> list[str]:
    names, makers = identities(catalog, registry)
    _, views = product_views(catalog, registry, schema, checked, media_url, (),
                             [p.id for p in catalog.all(Product) if p.id in names and p.id in makers])
    return [pid for pid, view in views.items() if not view.indexable]

def _pages(registry: Registry, views: dict[str, ProductView], checked: Check) -> dict[str, list[View]]:
    by_category: dict[str, list[View]] = {}
    for v in views.values():
        by_category.setdefault(v.category, []).append(listing_card(registry, v))
    return {c: [checked(plain(page), "CategoryPage", f"{c}/{page.page}") for page in paginate(registry, c, cards)]
            for c, cards in by_category.items()}

def build(catalog: Catalog, registry: Registry, schema: ModelSchema, log: ChangeLog, checked: Check,
          media_url: MediaUrl) -> ReadModel:
    versions = Projection(log)
    revised = listed(schema, log.after().changes)
    builder, views = product_views(catalog, registry, schema, checked, media_url, revised)
    pages = _pages(registry, views, checked)
    ownership = OwnershipHistory(catalog, registry)
    orgs = sorted(catalog.all(Organization), key=lambda o: o.slug)
    organizations = {o.slug: checked(plain(organization_view(o, builder, ownership)), "OrganizationView", o.slug)
                     for o in orgs}
    histories = {pid: plain(product_history(versions, pid, revised[pid], catalog, builder.terms.source_view))
                 for pid in views if pid in revised}
    tally = sum((Tally.of(v) for v in views.values()), Tally())
    cited = Cited(plain(views), {o.id: plain(brief(o)) for o in orgs},
                  {s.id: builder.terms.source_view(s) for s in catalog.all(Source)})
    articles, feed = news(catalog.all(FeedItem), cited, registry, checked)
    briefs = [brief(o) for o in orgs]
    idx = checked(plain(index(registry, [index_card(v) for v in views.values()], briefs,
                              {c: len(p) for c, p in pages.items()}, tally, feed.items)), "IndexView", "index")
    counted = checked(market(idx["products"], plain(briefs), list(catalog.all(OrgRelation)), registry), "MarketView",
                      "market")
    model = ReadModel(idx, views, pages, organizations, histories, tally, articles, feed, counted)
    checked(model.registry, "RegistryView", "registry")
    return model
