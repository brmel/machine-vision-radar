from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from radar.domain.model.entities import IndexView, Organization, ProductCard
from radar.domain.ports.catalog.catalog_repository import CatalogRepository

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
    url: str
    products: tuple[ProductCard, ...]
    target_product: str | None = None

def _product(key: str, index: IndexView) -> ProductCard:
    found = next((p for p in index.products if key in (p.id, p.slug) or p.slug.endswith(f"__{key}")), None)
    if found is None:
        raise LookupError(f"no product {key}")
    return found

def _product_site(key: str, orgs: Sequence[Organization], read: CatalogRepository) -> Site:
    prod = _product(key, read.index())
    if not (maker := next((o for o in orgs if o.slug == prod.vendor), None)):
        raise LookupError(f"no organization for product {key}")
    shown = read.product(prod.id)
    if not (url := (shown.website_url if shown else None) or maker.website):
        raise ValueError(f"{key}: has no website to read")
    return Site(maker.id, url, (prod,), target_product=prod.id)

def _maker_sites(makers: Sequence[Organization], index: IndexView, category: str | None, key: str) -> tuple[Site, ...]:
    sites = tuple(Site(o.id, o.website,
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

def sites_of(scope: RunScope, orgs: Sequence[Organization], read: CatalogRepository) -> tuple[Site, ...]:
    match scope:
        case ProductScope(key):
            return (_product_site(key, orgs, read),)
        case MakerScope(key):
            return _maker_sites(_named_makers(key, orgs), read.index(), None, key)
        case CategoryScope(key):
            index = read.index()
            return _maker_sites(_category_makers(key, orgs, index), index, key, key)
