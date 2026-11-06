from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from radar.domain.model.entities import IndexView, Instant, OrgRelation, Organization, ProductCard
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.web.reader import Link, Page, Reader, Unread

FOLLOW = 5

@dataclass(frozen=True, slots=True)
class ProductScope:
    key: str

@dataclass(frozen=True, slots=True)
class MakerScope:
    key: str

@dataclass(frozen=True, slots=True)
class CategoryScope:
    key: str

RunScope = ProductScope | MakerScope | CategoryScope

@dataclass(frozen=True, slots=True)
class Site:
    org: str
    home: str
    sites: tuple[str, ...]
    products: tuple[ProductCard, ...]
    target_product: str | None = None

@dataclass(frozen=True, slots=True)
class Reach:
    site: Site
    link: Link
    own: frozenset[str]
    home: bool = False

def _group(org: Organization, orgs: Sequence[Organization], owning: Sequence[OrgRelation]) -> tuple[str, ...]:
    tied = {r.to_org if r.from_org == org.id else r.from_org for r in owning if org.id in (r.from_org, r.to_org)}
    return tuple(o.website for o in orgs if o.id in tied and o.website)

def _product(key: str, index: IndexView) -> ProductCard:
    found = next((p for p in index.products if key in (p.id, p.slug) or p.slug.endswith(f"__{key}")), None)
    if found is None:
        raise LookupError(f"no product {key}")
    return found

def _product_site(key: str, orgs: Sequence[Organization], owning: Sequence[OrgRelation],
                  read: CatalogRepository) -> Site:
    prod = _product(key, read.index())
    if not (maker := next((o for o in orgs if o.slug == prod.vendor), None)):
        raise LookupError(f"no organization for product {key}")
    shown = read.product(prod.id)
    if not (url := (shown.website_url if shown else None) or maker.website):
        raise ValueError(f"{key}: has no website to read")
    sites = tuple(a for a in (url, maker.website, *_group(maker, orgs, owning)) if a)
    return Site(maker.id, url, sites, (prod,), target_product=prod.id)

def _maker_sites(makers: Sequence[Organization], orgs: Sequence[Organization], owning: Sequence[OrgRelation],
                 index: IndexView, category: str | None, key: str) -> tuple[Site, ...]:
    sites = tuple(Site(o.id, o.website, (o.website, *_group(o, orgs, owning)),
                       tuple(p for p in index.products if p.vendor == o.slug and category in (None, p.category)))
                  for o in makers if o.website)
    if not sites:
        raise ValueError(f"{key}: no maker in it has a website to read")
    return sites

def _named_makers(key: str, orgs: Sequence[Organization]) -> list[Organization]:
    named = [o for o in orgs if key in (o.id, o.slug)]
    if not named:
        raise LookupError(f"no organization {key}")
    return named

def _category_makers(key: str, orgs: Sequence[Organization], index: IndexView) -> list[Organization]:
    if key not in {c.id for c in index.categories}:
        raise LookupError(f"no category {key}")
    return [o for o in orgs if any(p.vendor == o.slug and p.category == key for p in index.products)]

def sites_of(scope: RunScope, orgs: Sequence[Organization], owning: Sequence[OrgRelation],
             read: CatalogRepository) -> tuple[Site, ...]:
    match scope:
        case ProductScope(key):
            return (_product_site(key, orgs, owning, read),)
        case MakerScope(key):
            return _maker_sites(_named_makers(key, orgs), orgs, owning, read.index(), None, key)
        case CategoryScope(key):
            index = read.index()
            return _maker_sites(_category_makers(key, orgs, index), orgs, owning, index, key, key)

class Frontier:
    def __init__(self, reader: Reader, sites: tuple[Site, ...]) -> None:
        self._reader = reader
        self._reach: list[Reach | Unread] = [self._home(s) for s in sites]
        self._seen: set[str] = set()
        self._mapped: set[str] = set()

    def _home(self, site: Site) -> Reach | Unread:
        home = self._reader.link(site.home)
        own = frozenset(link.site for link in map(self._reader.link, site.sites) if isinstance(link, Link))
        return home if isinstance(home, Unread) else Reach(site, home, own | {home.site}, home=True)

    def next(self) -> Reach | Unread | None:
        while self._reach:
            reach = self._reach.pop(0)
            if isinstance(reach, Unread):
                return reach
            if reach.link.address not in self._seen:
                self._seen.add(reach.link.address)
                return reach
        return None

    def mapped(self, reach: Reach, by: Instant) -> Unread | None:
        if reach.site.target_product or reach.link.site in self._mapped:
            return None
        self._mapped.add(reach.link.site)
        seeds = self._reader.sitemap(reach.link, by)
        if isinstance(seeds, Unread):
            return seeds
        self._reach += sorted((Reach(reach.site, s, reach.own) for s in seeds if s.within(reach.own)),
                              key=lambda seed: seed.link.site == reach.link.site)
        return None

    def read(self, reach: Reach, page: Page, follow: tuple[str, ...]) -> None:
        self._seen.add(page.link.address)
        held = {link.address: link for link in page.links}
        named = [held[a] for a in dict.fromkeys(follow) if a in held and a not in self._seen]
        self._reach += [Reach(reach.site, link, reach.own) for link in named if link.within(reach.own)][:FOLLOW]
