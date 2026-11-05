from __future__ import annotations

import json
from typing import Collection, Iterable, Mapping, Sequence

from radar.adapters.files.json_parser import Checker
from radar.adapters.storage.blobs import media_url
from radar.domain.ports.catalog.views import Check
from radar.domain.read_model import read_model
from radar.domain.read_model.history import listed, product_history
from radar.domain.read_model.listings import Tally, index, index_card, listing_card, paginate
from radar.domain.read_model.listings import parse_card
from radar.domain.read_model.organizations import brief, organization_view
from radar.domain.read_model.products.views import ProductViews
from radar.domain.read_model.derived.market import market
from radar.domain.read_model.derived.ownership import OwnershipHistory
from radar.domain.review.feed.news import Cited, news
from radar.adapters.storage.memory_change_log import MemoryChangeLog
from radar.domain.model.history.projection import Projection, plain
from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import (Change, FeedBrief, FeedItem, ModelRow, OrgBrief, Organization, OrgRelation,
                                         Product, ProductView, Source)
from radar.domain.model.model import Model
from radar.domain.ports.store.docs import Docs, Fields
from ..layout import (FACETS, HISTORY, INDEX, NEWS, ORGANIZATIONS, PAGES, PRODUCTS, Record, catalog_of, chunks, doc,
                      doc_value, index_docs, listing_docs, news_docs, product_doc, public_docs, read_records)
from .neighborhood import Changed, Neighborhood, of_kind

Writes = dict[str, Fields | None]

def _reached(items: Sequence[FeedItem], touched: set[str]) -> set[str]:
    return {i.slug for i in items if {i.id, *i.cites} & touched}

def _page_counts(registry: Record, pages: Writes) -> dict[str, int]:
    counts = {c["id"]: c["pages"] for c in registry.get("categories", [])}
    return {**counts, **{k.split("/")[1]: v["pages"] if v else 0 for k, v in pages.items() if k.count("/") == 1}}

def _teaser(stored: Record, briefs: Sequence[FeedBrief] | None, checked: Checker) -> Sequence[FeedBrief]:
    return briefs if briefs is not None else [checked.parse(b, FeedBrief, b["slug"]) for b in stored.get("news", [])]

def _kept(old: Mapping[str, ProductView], rebuilt: Collection[str]) -> dict[str, list[ModelRow]]:
    return {p: [m for m in v.models if m.id not in rebuilt] for p, v in old.items()}

def full(catalog: Catalog, model: Model, changes: Sequence[Change]) -> dict[str, Fields]:
    return public_docs(read_model.build(catalog, model, MemoryChangeLog(changes), Checker(model), media_url))

class Projector:
    def __init__(self, docs: Docs, model: Model) -> None:
        self.docs, self.model, self.schema, self.registry = docs, model, model.schema, model.registry
        schema = model.schema
        self.product, self.organization, self.feed, self.source, self.relation = (
            schema.types[t.__name__].prefix for t in (Product, Organization, FeedItem, Source, OrgRelation))
        self.feed_items, self.relations = schema.collection(FeedItem.__name__), schema.collection(OrgRelation.__name__)

    def writes(self, hood: Neighborhood, changed: Changed) -> Writes:
        records = hood.after(changed)
        catalog = catalog_of(self.model, records.values())
        checked = Checker(self.model)
        present = sorted(p for p in hood.products if p in records)
        changes = sorted(catalog.all(Change), key=lambda c: (c.entity, c.version))
        revised = listed(self.schema, changes)
        old = {p: checked.parse(doc_value(f), ProductView, p)
               for p, f in ((p, self.docs.get(f"{PRODUCTS}/{p}")) for p in sorted(hood.products)) if f}
        builder, views = read_model.product_views(catalog, self.model, checked, media_url, revised,
                                                  present, _kept(old, hood.products))
        out: Writes = {f"{PRODUCTS}/{p}": product_doc(views[p]) if p in views else None for p in hood.products}
        pages = self._listings(views, old, checked)
        out.update(pages)
        out.update(self._histories(hood, views, catalog, changes, revised, builder))
        out.update(self._organization_docs(hood, changed, catalog, builder, checked))
        articles, briefs = self._news(hood, changed, views, builder, checked)
        out.update(articles)
        orgs = self._briefs({i: (b, a) for i, (b, a) in changed.items() if i.startswith(f"{self.organization}_")})
        out.update(self._index(views, old, orgs, pages, changed, checked, briefs))
        return out

    def _after(self, prefix: str, ids: Iterable[str], changed: Changed) -> list[Record]:
        stored = read_records(self.docs, self.schema, [i for i in ids if i not in changed])
        return [*stored.values(),
                *(a for i, (_, a) in changed.items() if i.startswith(f"{prefix}_") and a is not None and i in ids)]

    def _cited(self, refs: set[str], changed: Changed, views: Mapping[str, ProductView],
               builder: ProductViews) -> Cited:
        stored = self.docs.get_many([f"{PRODUCTS}/{r}" for r in of_kind(self.product, refs) if r not in views])
        products = {path.split("/", 1)[1]: doc_value(f) for path, f in stored.items()}
        briefs = {b["id"]: b for b in doc_value(self.docs.get(f"{INDEX}/organizations")) or []}
        orgs = catalog_of(self.model,
                          self._after(self.organization, of_kind(self.organization, changed.keys()),
                                      changed)).all(Organization)
        sources = catalog_of(self.model, self._after(self.source, of_kind(self.source, refs), changed)).all(Source)
        return Cited({**products, **plain(views)},
                     {**briefs, **{o.id: plain(brief(o)) for o in orgs}},
                     {s.id: builder.terms.source_view(s) for s in sources})

    def _news(self, hood: Neighborhood, changed: Changed, views: Mapping[str, ProductView], builder: ProductViews,
              checked: Check) -> tuple[Writes, Sequence[FeedBrief] | None]:
        ids = {f["id"] for _, f in self.docs.list(self.feed_items)} | of_kind(self.feed, changed.keys())
        items = catalog_of(self.model, self._after(self.feed, ids, changed)).all(FeedItem)
        reached = _reached(items, changed.keys() | hood.products | hood.organizations)
        if not reached and not of_kind(self.feed, changed.keys()):
            return {}, None
        articles, feed = news(items, self._cited({c for i in items for c in i.cites}, changed, views, builder),
                              self.registry, checked)
        gone = {p: None for p, _ in self.docs.list(NEWS) if p.split("/", 1)[1] not in articles}
        return {**gone, **news_docs({s: v for s, v in articles.items() if s in reached}, feed)}, feed.items

    def _histories(self, hood: Neighborhood, views: Mapping[str, ProductView], catalog: Catalog,
                   changes: Sequence[Change], revised: Mapping[str, Mapping[str, str | None]],
                   builder: ProductViews) -> Writes:
        versions = Projection(MemoryChangeLog(changes))
        return {f"{HISTORY}/{p}": doc(
            plain(product_history(versions, p, revised[p], catalog, builder.terms.source_view)))
                if p in views and p in revised else None for p in hood.products}

    def _organization_docs(self, hood: Neighborhood, changed: Changed, catalog: Catalog, builder: ProductViews,
                           checked: Check) -> Writes:
        orgs = {o.id: o for o in catalog.all(Organization) if o.id in hood.organizations}
        out: Writes = {}
        for oid in hood.organizations:
            before = changed.get(oid, (hood.records.get(oid), None))[0]
            if before is not None and (oid not in orgs or orgs[oid].slug != before["slug"]):
                out[f"{ORGANIZATIONS}/{before['slug']}"] = None
        ownership = OwnershipHistory(catalog, self.registry)
        out.update({f"{ORGANIZATIONS}/{o.slug}": doc(checked(plain(organization_view(o, builder, ownership)),
                                                             "OrganizationView", o.slug)) for o in orgs.values()})
        return out

    def _listings(self, views: Mapping[str, ProductView], old: Mapping[str, ProductView], checked: Check) -> Writes:
        categories = sorted({v.category for v in (*views.values(), *old.values())})
        return {path: fields for c in categories for path, fields in self._listing(c, views, old, checked).items()}

    def _listing(self, category: str, views: Mapping[str, ProductView], old: Mapping[str, ProductView],
                 checked: Check) -> Writes:
        stored = dict(self.docs.list(f"{FACETS}/{category}/{PAGES}"))
        cards = [parse_card(c) for f in stored.values() for c in doc_value(f)["products"] if c["id"] not in old
                 and c["id"] not in views]
        cards += [listing_card(self.registry, v) for v in views.values() if v.category == category]
        if not cards:
            return {**dict.fromkeys(stored), f"{FACETS}/{category}": None}
        fresh = listing_docs(category,
                             [checked(plain(p), "CategoryPage", f"{category}/{p.page}")
                              for p in paginate(self.registry, category, cards)])
        return {**dict.fromkeys(stored.keys() - fresh.keys()), **fresh}

    def _briefs(self, orgs: Changed) -> list[Record]:
        briefs = {b["id"]: b for b in doc_value(self.docs.get(f"{INDEX}/organizations")) or [] if b["id"] not in orgs}
        briefs.update({oid: plain(brief(catalog_of(self.model, [after]).get(oid))) for oid, (_, after) in orgs.items()
                       if after is not None})
        return sorted(briefs.values(), key=lambda b: b["slug"])

    def _market(self, cards: list[Record], orgs: list[Record], changed: Changed, checked: Check) -> Writes:
        ids = {f["id"] for _, f in self.docs.list(self.relations)} | of_kind(self.relation, changed.keys())
        relations = catalog_of(self.model, self._after(self.relation, ids, changed)).all(OrgRelation)
        return {f"{INDEX}/market": doc(checked(market(cards, orgs, list(relations), self.registry), "MarketView",
                                               "market"))}

    def _index(self, views: Mapping[str, ProductView], old: Mapping[str, ProductView], orgs: list[Record],
               pages: Writes, changed: Changed, checked: Checker, news_briefs: Sequence[FeedBrief] | None) -> Writes:
        reg = self.docs.get(f"{INDEX}/registry") or {"json": "{}", "cards": 0, "tally": json.dumps(Tally().plain())}
        stored = doc_value(reg)
        gone = old.keys() | views.keys()
        cards = [parse_card(c) for n in range(1, reg["cards"] + 1)
                 for c in doc_value(self.docs.get(f"{INDEX}/cards-{n}")) if c["id"] not in gone]
        cards += [index_card(v) for v in views.values()]
        tally = Tally.parse(json.loads(reg["tally"])) - sum((Tally.of(v) for v in old.values()), Tally()) + sum(
            (Tally.of(v) for v in views.values()), Tally())
        briefs = [checked.parse(b, OrgBrief, b["id"]) for b in orgs]
        idx = checked(plain(index(self.registry, cards, briefs, _page_counts(stored, pages), tally,
                                  _teaser(stored, news_briefs, checked))), "IndexView", "index")
        return {**index_docs(idx, tally), **self._market(idx["products"], orgs, changed, checked),
                **{f"{INDEX}/cards-{n}": None for n in range(len(chunks(idx["products"])) + 1, reg["cards"] + 1)}}
