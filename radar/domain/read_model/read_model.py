from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Collection, Iterable, Mapping, Sequence

from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import (CategoryPage, FeedItem, FeedItemView, FeedPageView, HistoryView, IndexView,
                                         MarketView, ModelRow, Organization, OrganizationView, OrgRelation, Product,
                                         ProductCard, ProductView, RegistryView, Source)
from radar.domain.model.history.projection import Projection, plain
from radar.domain.model.registry import Registry
from radar.domain.ports.catalog.views import MediaUrl
from radar.domain.ports.history.change_log import ChangeLog
from radar.domain.read_model.derived.coverage import Coverage
from radar.domain.read_model.derived.market import market
from radar.domain.read_model.derived.provenance import Provenance
from radar.domain.read_model.derived.ownership import OwnershipHistory
from .history import listed, product_history
from .listings import Tally, index, index_card, listing_card, paginate, registry_view
from .organizations import brief, organization_view
from .products.views import ProductViews
from radar.domain.review.feed.news import Cited, news
from radar.domain.read_model.derived.identity import identities

if TYPE_CHECKING:
    from radar.domain.model.model import Model

@dataclass(frozen=True, slots=True)
class ReadModel:
    index: IndexView
    products: dict[str, ProductView]
    pages: dict[str, list[CategoryPage]]
    organizations: dict[str, OrganizationView]
    histories: dict[str, HistoryView]
    tally: Tally
    news: dict[str, FeedItemView]
    feed: FeedPageView
    market: MarketView

    @property
    def registry(self) -> RegistryView:
        return registry_view(self.index)

def product_views(catalog: Catalog, model: Model, media_url: MediaUrl,
                  revised: Collection[str], ids: Iterable[str] | None = None,
                  kept: Mapping[str, Sequence[ModelRow]] | None = None) -> tuple[ProductViews, dict[str, ProductView]]:
    orgs = {o.id: o for o in catalog.all(Organization)}
    products = {p.id: p for p in catalog.all(Product)}
    wanted = sorted(products if ids is None else ids)
    names, makers = identities(catalog, model.registry)
    missing = [pid for pid in wanted if pid not in makers or pid not in names]
    if missing:
        raise ValueError(f"product {missing[0]} has no vendor role or no primary name")
    builder = ProductViews(catalog, model.registry, model.schema, products, media_url, wanted, kept)
    views = {pid: builder.view(products[pid], names, brief(orgs[makers[pid]]), pid in revised) for pid in wanted}
    return builder, views

def thin(catalog: Catalog, model: Model, media_url: MediaUrl) -> list[str]:
    names, makers = identities(catalog, model.registry)
    _, views = product_views(catalog, model, media_url, (),
                             [p.id for p in catalog.all(Product) if p.id in names and p.id in makers])
    return [pid for pid, view in views.items() if not view.indexable]

@dataclass(frozen=True, slots=True)
class Quality:
    provenance: tuple[Provenance, ...]
    names: dict[str, str]
    coverage: Coverage

def quality(catalog: Catalog, model: Model, media_url: MediaUrl, today: date) -> Quality:
    return Quality(tuple(Provenance.of(catalog, model.registry, today)), identities(catalog, model.registry)[0],
                   Coverage.of(catalog, model.registry, thin(catalog, model, media_url)))

def _pages(registry: Registry, views: dict[str, ProductView]) -> dict[str, list[CategoryPage]]:
    by_category: dict[str, list[ProductCard]] = {}
    for v in views.values():
        by_category.setdefault(v.category, []).append(listing_card(registry, v))
    return {c: paginate(registry, c, cards) for c, cards in by_category.items()}

def build(catalog: Catalog, model: Model, log: ChangeLog, media_url: MediaUrl) -> ReadModel:
    versions, registry = Projection(log), model.registry
    revised = listed(model.schema, log.after().changes)
    builder, views = product_views(catalog, model, media_url, revised)
    pages = _pages(registry, views)
    ownership = OwnershipHistory(catalog, registry)
    orgs = sorted(catalog.all(Organization), key=lambda o: o.slug)
    organizations = {o.slug: organization_view(o, builder, ownership) for o in orgs}
    histories = {pid: product_history(versions, pid, revised[pid], catalog, builder.terms.source_view)
                 for pid in views if pid in revised}
    tally = sum((Tally.of(v) for v in views.values()), Tally())
    cited = Cited(plain(views), {o.id: plain(brief(o)) for o in orgs},
                  {s.id: builder.terms.source_view(s) for s in catalog.all(Source)})
    articles, feed = news(catalog.all(FeedItem), cited, registry)
    briefs = [brief(o) for o in orgs]
    indexed = index(registry, [index_card(v) for v in views.values()], briefs, {c: len(p) for c, p in pages.items()},
                    tally, feed.items)
    counted = market(indexed.products, briefs, list(catalog.all(OrgRelation)), registry)
    return ReadModel(indexed, views, pages, organizations, histories, tally, articles, feed, counted)
