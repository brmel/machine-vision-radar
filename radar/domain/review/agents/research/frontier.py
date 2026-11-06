from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Callable, Mapping, Sequence

from radar.domain.model.entities import (FrontierView, IndexView, Instant, OrgRelation, Organization, ProductCard,
                                         RunScope, RunScopeKind, Term)
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.web.crawl_records import CrawlRecord, CrawlRecords, CrawlStatus, PageKind
from radar.domain.ports.web.reader import Link, Page, Reader, Unread

FOLLOW, VIEWED = 5, 20
READ_AGAIN, RETRY = timedelta(days=30), timedelta(days=7)
PRODUCT_PAGE = re.compile(r"/(products?|produits?|produkte?|models?|catalog|catalogue|shop)(/|$)", re.I)
LANGUAGE_COPY = re.compile(r"^(https?://[^/]+)/([a-z]{2})(?:[-_][a-z]{2})?(/.*)$", re.I)

def _later(now: Instant, by: timedelta) -> Instant:
    return (datetime.fromisoformat(now) + by).strftime("%Y-%m-%dT%H:%M:%SZ")

def _hashed(page: Page) -> str:
    return hashlib.sha256(page.text.encode()).hexdigest()

def one_copy(links: Sequence[Link], language: str) -> tuple[Link, ...]:
    kept: dict[str, Link] = {}
    for link in links:
        copy = LANGUAGE_COPY.match(link.address)
        page = f"{copy.group(1)}{copy.group(3)}" if copy else link.address
        if page not in kept or not copy or copy.group(2).casefold() == language:
            kept[page] = link
    return tuple(kept.values())

@dataclass(frozen=True, slots=True)
class Site:
    org: str
    home: str
    sites: tuple[str, ...]
    products: tuple[ProductCard, ...]
    one_product: bool = False

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
    return Site(maker.id, url, sites, (prod,), one_product=True)

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
    key = scope.key
    match scope.kind:
        case RunScopeKind.PRODUCT:
            return (_product_site(key, orgs, owning, read),)
        case RunScopeKind.MAKER:
            return _maker_sites(_named_makers(key, orgs), orgs, owning, read.index(), None, key)
        case RunScopeKind.CATEGORY:
            index = read.index()
            return _maker_sites(_category_makers(key, orgs, index), orgs, owning, index, key, key)

class SourceTypes:
    def __init__(self, types: Mapping[str, Term]) -> None:
        self._own = next(k for k, t in types.items() if t.research)
        self._hosts = tuple((host, k) for k, t in types.items() for host in t.hosts or ())
        self._third_party = next(k for k, t in types.items() if t.third_party)

    def of(self, link: Link, own: frozenset[str], kind: str | None = None) -> str:
        if link.within(own):
            return kind or self._own
        return next((k for host, k in self._hosts if link.within((host,))), self._third_party)

class Frontier:
    def __init__(self, reader: Reader, sites: tuple[Site, ...], crawl: CrawlRecords, language: str,
                 now: Callable[[], Instant]) -> None:
        self._reader, self._crawl, self._language, self._now = reader, crawl, language, now
        self._held: dict[str, dict[str, CrawlRecord]] = {}
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
        if reach.site.one_product or reach.link.site in self._mapped:
            return None
        self._mapped.add(reach.link.site)
        held = self._records(reach.site.org)
        if not any(r.site == reach.link.site for r in held.values()) and (unread := self.seed(reach, by)):
            return unread
        self._reach += [Reach(reach.site, Link(r.address, r.site), reach.own) for r in self._due(reach, held)]
        return None

    def _due(self, reach: Reach, held: Mapping[str, CrawlRecord]) -> list[CrawlRecord]:
        now = self._now()
        due = (r for r in held.values() if r.next_due <= now and r.address != reach.link.address)
        return sorted(due, key=lambda r: (r.kind is not PageKind.PRODUCT, r.site == reach.link.site, r.next_due))

    def seed(self, reach: Reach, by: Instant) -> Unread | None:
        seeds = self._reader.sitemap(reach.link, by)
        if isinstance(seeds, Unread):
            return seeds
        held = self._records(reach.site.org)
        fresh = [self._record(s, reach.site.org) for s in one_copy(seeds, self._language)
                 if s.within(reach.own) and s.address not in held]
        self._crawl.save(fresh)
        held.update({r.address: r for r in fresh})
        return None

    def _records(self, org: str) -> dict[str, CrawlRecord]:
        return self._held.setdefault(org, {r.address: r for r in self._crawl.listed(org)})

    def _record(self, link: Link, org: str) -> CrawlRecord:
        kind = PageKind.PRODUCT if PRODUCT_PAGE.search(link.address) else PageKind.OTHER
        return CrawlRecord(link.address, link.site, org, kind, CrawlStatus.DUE, self._now())

    def unchanged(self, reach: Reach, page: Page) -> bool:
        if reach.site.one_product:
            return False
        held = self._records(reach.site.org).get(page.link.address)
        return bool(held and held.content_hash == _hashed(page))

    def unread(self, reach: Reach, unread: Unread) -> None:
        if not reach.site.one_product:
            self._saved(reach, replace(self._of(reach), status=CrawlStatus.UNREAD, reason=unread.reason,
                                       fetched_at=self._now(), next_due=_later(self._now(), RETRY)))

    def _of(self, reach: Reach) -> CrawlRecord:
        return (self._records(reach.site.org).get(reach.link.address)
                or self._record(reach.link, reach.site.org))

    def _saved(self, reach: Reach, record: CrawlRecord) -> None:
        self._records(reach.site.org)[record.address] = record
        self._crawl.save((record,))

    def read(self, reach: Reach, page: Page, follow: tuple[str, ...]) -> None:
        self._seen.add(page.link.address)
        kept = self._followed(reach, page, follow)
        self._reach += [Reach(reach.site, link, reach.own) for link in kept]
        if not reach.site.one_product:
            self._remember(reach, page, kept)

    def _followed(self, reach: Reach, page: Page, follow: tuple[str, ...]) -> list[Link]:
        held = {link.address: link for link in page.links}
        named = [held[a] for a in dict.fromkeys(follow) if a in held and a not in self._seen]
        return [link for link in named if link.within(reach.own)][:FOLLOW]

    def _remember(self, reach: Reach, page: Page, kept: list[Link]) -> None:
        known = self._records(reach.site.org)
        self._crawl.save([self._record(link, reach.site.org) for link in kept if link.address not in known])
        self._saved(reach, replace(self._of(reach), status=CrawlStatus.READ, reason=None, fetched_at=self._now(),
                                   content_hash=_hashed(page), next_due=_later(self._now(), READ_AGAIN)))

    def view(self, org: str) -> FrontierView:
        held = self._records(org).values()
        now = self._now()
        due = sorted((r for r in held if r.next_due <= now), key=lambda r: (r.kind is not PageKind.PRODUCT, r.next_due))
        return FrontierView(org=org, total=len(held), due=len(due),
                            read=sum(r.status is CrawlStatus.READ for r in held),
                            unread=sum(r.status is CrawlStatus.UNREAD for r in held),
                            next=tuple(r.address for r in due[:VIEWED]))
