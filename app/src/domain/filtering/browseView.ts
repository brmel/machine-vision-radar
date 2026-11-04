import type { ListingPage, ListingQuery } from "../ports/CatalogRepository.ts";
import type { CategoryPage, FacetView, IndexView, ProductCard } from "../views.ts";
import { byColumn, extractSpecOptionIds, offersAny, overlaps } from "./filter.ts";
import type { BrowseFilters } from "./filterUrl.ts";
import { withCategory, withDomain, withStage } from "./filterTransitions.ts";
import { pageCount } from "../paths.ts";

export type BrowseIndex = Omit<IndexView, "products">;

export interface BrowseView {
  readonly filters: BrowseFilters;
  readonly dropped: readonly string[];
  readonly resultCount: number;
  readonly page: number;
  readonly totalPages: number;
  readonly products: readonly ProductCard[];
  readonly facets: readonly FacetView[];
  readonly categoryFacets: readonly FacetView[];
  readonly domainCounts: Readonly<Record<string, number>>;
  readonly stageCounts: Readonly<Record<string, number>>;
  readonly categoryCounts: Readonly<Record<string, number>>;
}

export type Listing =
  | { readonly kind: "all"; readonly facets: readonly FacetView[]; readonly products: readonly ProductCard[] }
  | { readonly kind: "page"; readonly page: CategoryPage }
  | { readonly kind: "query"; readonly page: ListingPage };

type Order = (a: ProductCard, b: ProductCard) => number;

export const listingOrder = (sort: ListingQuery["sort"]): Order => (a, b) => {
  const keys = (c: ProductCard): string[] =>
    [...(sort === "vendor" ? [c.vendor_name.toLowerCase()] : []), c.name.toLowerCase(), c.id];
  const [x, y] = [keys(a), keys(b)];
  const n = x.findIndex((k, i) => k !== y[i]);
  const order = n === -1 ? 0 : x[n] < y[n] ? -1 : 1;
  return sort === "name-desc" ? -order : order;
};

const ORDER: Record<BrowseFilters["sort"], Order | null> = {
  relevance: null,
  name: listingOrder("name"),
  "name-desc": listingOrder("name-desc"),
  vendor: listingOrder("vendor"),
};

const keeps = (f: BrowseFilters, c: BrowseIndex["categories"][number]): boolean =>
  (!f.category || c.id === f.category) && (!f.domain || c.domain === f.domain)
    && (!f.stage || c.pipeline.includes(f.stage));

function matching(products: readonly ProductCard[], f: BrowseFilters,
    categories: BrowseIndex["categories"]): ProductCard[] {
  const kept = new Set(categories.filter((c) => keeps(f, c)).map((c) => c.id));
  const specs = Object.entries(f.specs);
  const ranges = Object.entries(f.ranges);
  return products.filter((p) => kept.has(p.category)
    && specs.every(([key, selected]) => offersAny(p.specs[key], selected))
    && ranges.every(([key, range]) => overlaps(p.specs[key], range)));
}

export function needsWholeCategory(filters: BrowseFilters): boolean {
  return Object.keys(filters.specs).length > 0 || Object.keys(filters.ranges).length > 0 || filters.sort !== "name"
    || filters.column !== null;
}

export function listingQuery(filters: BrowseFilters, categories: BrowseIndex["categories"]): ListingQuery {
  const narrowed = filters.domain !== null || filters.stage !== null;
  return { ...(narrowed ? { categories: categories.filter((c) => keeps(filters, c)).map((c) => c.id) } : {}),
    sort: filters.sort === "relevance" ? "name" : filters.sort };
}

function liveFacets(facets: readonly FacetView[], products: readonly ProductCard[], filters: BrowseFilters,
    index: BrowseIndex): FacetView[] {
  return facets
    .map((facet) => {
      const others = { ...filters,
        specs: Object.fromEntries(Object.entries(filters.specs).filter(([key]) => key !== facet.spec_key)),
        ranges: Object.fromEntries(Object.entries(filters.ranges).filter(([key]) => key !== facet.spec_key)) };
      const counts = new Map<string, number>();
      for (const product of matching(products, others, index.categories)) {
        for (const id of new Set(extractSpecOptionIds(product.specs[facet.spec_key])))
          counts.set(id, (counts.get(id) ?? 0) + 1);
      }
      return { ...facet, options: facet.options.map((o) => ({ ...o, count: counts.get(o.id.toLowerCase()) ?? 0 }))
        .filter((o) => o.count > 0) };
    })
    .filter((facet) => facet.options.length > 0 || facet.spec_key in filters.ranges);
}

function sized(f: BrowseFilters, categories: BrowseIndex["categories"]): number {
  return categories.filter((c) => keeps(f, c)).reduce((sum, c) => sum + c.products, 0);
}

export function browseView(index: BrowseIndex, filters: BrowseFilters, dropped: readonly string[], listing: Listing,
    pageSize: number): BrowseView {
  const { categories } = index;
  const count = (f: BrowseFilters): number =>
    listing.kind === "all" && (filters.q !== "" || f.category === filters.category)
      ? matching(listing.products, f, categories).length : sized(f, categories);
  const countEach = (ids: readonly string[], select: (id: string) => BrowseFilters): Record<string, number> =>
    Object.fromEntries(ids.map((id) => [id, count(select(id))]));
  const counts = {
    domainCounts: countEach([...new Set(categories.map((c) => c.domain))], (d) => withDomain(filters, d, categories)),
    stageCounts: countEach(index.pipeline_stages.map((s) => s.id), (p) => withStage(filters, p, categories)),
    categoryCounts: countEach(categories.map((c) => c.id), (id) => withCategory(filters, id, categories)),
  };
  if (listing.kind === "page") {
    const { page } = listing;
    const category = categories.find((c) => c.id === page.category);
    return {
      filters: { ...filters, page: page.page }, dropped, resultCount: category?.products ?? page.products.length,
      page: page.page, totalPages: page.pages, products: page.products, facets: page.facets,
      categoryFacets: page.facets, ...counts,
    };
  }
  if (listing.kind === "query") {
    const totalPages = pageCount(listing.page.total, pageSize);
    const page = Math.min(filters.page, totalPages);
    return {
      filters: { ...filters, page }, dropped, resultCount: listing.page.total, page, totalPages,
      products: listing.page.products, facets: [], categoryFacets: [], ...counts,
    };
  }
  const order = ORDER[filters.sort];
  const filtered = matching(listing.products, filters, categories);
  const sorted = order ? filtered.sort(order) : filtered;
  const results = filters.column ? [...sorted].sort(byColumn(filters.column)) : sorted;
  const totalPages = pageCount(results.length, pageSize);
  const page = Math.min(filters.page, totalPages);
  return {
    filters: { ...filters, page },
    dropped,
    resultCount: results.length,
    page,
    totalPages,
    products: results.slice((page - 1) * pageSize, page * pageSize),
    facets: liveFacets(listing.facets, listing.products, filters, index),
    categoryFacets: listing.facets,
    ...counts,
  };
}
