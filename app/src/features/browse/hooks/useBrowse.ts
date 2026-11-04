import { useEffect } from "react";
import { PAGE_SIZE, type CatalogRepository } from "../../../domain/ports/CatalogRepository.ts";
import type { CategoryPage, Found } from "../../../domain/views.ts";
import { browseView, listingQuery, needsWholeCategory, type BrowseIndex, type BrowseView,
  type Listing } from "../../../domain/filtering/browseView.ts";
import { decodeFilters, encodeFilters, type BrowseFilters } from "../../../domain/filtering/filterUrl.ts";
import { logger } from "../../../shell/logger.ts";
import { useRead, type Read } from "../../../ui/index.ts";

interface Browse {
  index: BrowseIndex | null;
  view: BrowseView | null;
  searched: Found["ranking"] | null;
  error: "catalog" | "search" | null;
  change: (next: BrowseFilters) => void;
}

async function listingOf(reader: CatalogRepository, base: BrowseIndex, filters: BrowseFilters,
    first: CategoryPage | null): Promise<Listing> {
  if (!first || !filters.category) return { kind: "query",
    page: await reader.listing(listingQuery(filters, base.categories), filters.page, PAGE_SIZE) };
  const whole = needsWholeCategory(filters);
  const pages = [first];
  for (let next = first.next; next && (whole || pages.length < filters.page); next = pages[pages.length - 1].next)
    pages.push(await reader.categoryPage(filters.category, next));
  return whole ? { kind: "all", facets: first.facets, products: pages.flatMap((p) => p.products) }
    : { kind: "page", page: pages[pages.length - 1] };
}

type Browsed = { query: string; index: BrowseIndex; view: BrowseView; searched: Browse["searched"] }
  | { query: string; index: BrowseIndex; failed: "search" };

async function browsed(reader: CatalogRepository, rank: (words: string) => Promise<Found>,
    query: string): Promise<Browsed> {
  const [registry, organizations] = await Promise.all([reader.registry(), reader.organizations()]);
  const index = { ...registry, organizations };
  const category = new URLSearchParams(query).get("category");
  const first = category !== null && index.categories.some((c) => c.id === category)
    ? await reader.categoryPage(category) : null;
  const { filters, dropped } = decodeFilters(query,
    { categories: index.categories, stages: index.pipeline_stages.map((s) => s.id), facets: first?.facets ?? [] });
  if (!filters.q) return { query, index, view: browseView(index, filters, dropped,
    await listingOf(reader, index, filters, first), PAGE_SIZE), searched: null };
  const found = await rank(filters.q).catch((err: unknown) => {
    logger.error("browse: the search failed", { query }, err);
    return null;
  });
  if (!found) return { query, index, failed: "search" };
  const listing: Listing = { kind: "all", facets: first?.facets ?? [], products: found.products };
  return { query, index, view: browseView(index, filters, dropped, listing, PAGE_SIZE), searched: found.ranking };
}

function failure(read: Read<Browsed>, query: string): Browse["error"] {
  if (read.error) return "catalog";
  return read.value && "failed" in read.value && read.value.query === query ? read.value.failed : null;
}

export function useBrowse(
  reader: CatalogRepository,
  rank: (words: string) => Promise<Found>,
  query: string,
  navigate: (query: string, replace: boolean) => void,
): Browse {
  const read = useRead(() => browsed(reader, rank, query), `browse?${query}`,
    (err) => logger.error("browse: a listing page failed to load", { query }, err));
  const loaded = read.value && "view" in read.value ? read.value : null;
  const error = failure(read, query);

  const settled = loaded?.query === query ? loaded.view : null;

  useEffect(() => {
    if (!settled) return;
    const canonical = encodeFilters(settled.filters);
    if (settled.dropped.length > 0) logger.warn("browse: URL names filters the read model does not have; dropped",
      { dropped: settled.dropped.join(" ") });
    if (canonical !== query.replace(/^\?/, "")) navigate(canonical, true);
  }, [settled, query, navigate]);

  return { index: read.value?.index ?? null, view: loaded?.view ?? null, searched: loaded?.searched ?? null, error,
    change: (next) => navigate(encodeFilters(next), false) };
}
