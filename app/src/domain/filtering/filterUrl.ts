import type { CategoryEntry, FacetView } from "../views.ts";

export type BrowseSort = "relevance" | "name" | "name-desc" | "vendor";

export interface BrowseFilters {
  readonly q: string;
  readonly category: string | null;
  readonly domain: string | null;
  readonly stage: string | null;
  readonly specs: Readonly<Record<string, readonly string[]>>;
  readonly ranges: Readonly<Record<string, Range>>;
  readonly sort: BrowseSort;
  readonly column: ColumnSort | null;
  readonly layout: BrowseLayout;
  readonly page: number;
}

export type BrowseLayout = "cards" | "table";

export interface ColumnSort {
  readonly key: string;
  readonly desc: boolean;
}

export interface Range {
  readonly min?: number;
  readonly max?: number;
}

export const NO_FILTERS: BrowseFilters = { q: "", category: null, domain: null, stage: null, specs: {}, ranges: {},
  sort: "name", column: null, layout: "cards", page: 1 };

const BOUNDS = ["min", "max"] as const;

interface FilterVocabulary {
  readonly categories: readonly CategoryEntry[];
  readonly stages: readonly string[];
  readonly facets: readonly FacetView[];
}

export const SORTS: readonly BrowseSort[] = ["relevance", "name", "name-desc", "vendor"];
const FIXED_KEYS = ["q", "category", "domain", "stage", "sort", "view", "page"];

const list = (values: readonly string[]): string => [...values].sort().map(encodeURIComponent).join(",");

function facetPairs(filters: BrowseFilters): [string, string][] {
  const pairs: [string, string][] = [];
  for (const key of Object.keys(filters.specs).sort()) {
    if (filters.specs[key].length > 0) pairs.push([encodeURIComponent(key), list(filters.specs[key])]);
  }
  for (const key of Object.keys(filters.ranges).sort()) {
    for (const bound of BOUNDS) {
      const value = filters.ranges[key][bound];
      if (value !== undefined) pairs.push([`${encodeURIComponent(key)}_${bound}`, String(value)]);
    }
  }
  return pairs;
}

export function encodeFilters(filters: BrowseFilters): string {
  const pairs: [string, string][] = [];
  if (filters.category) pairs.push(["category", encodeURIComponent(filters.category)]);
  if (filters.q) pairs.push(["q", encodeURIComponent(filters.q)]);
  if (filters.domain) pairs.push(["domain", encodeURIComponent(filters.domain)]);
  if (filters.stage) pairs.push(["stage", filters.stage]);
  pairs.push(...facetPairs(filters));
  if (filters.column)
    pairs.push(["sort", `${encodeURIComponent(filters.column.key)}${filters.column.desc ? "-desc" : ""}`]);
  else if (filters.sort !== defaultSort(filters.q)) pairs.push(["sort", filters.sort]);
  if (filters.layout === "table") pairs.push(["view", "table"]);
  if (filters.page > 1) pairs.push(["page", String(filters.page)]);
  return pairs.map(([key, value]) => `${key}=${value}`).join("&");
}

export function boundOf(value: string): number | null {
  const number = Number(value.replace(",", "."));
  return value.trim() !== "" && Number.isFinite(number) ? number : null;
}

function decodeFacets(params: URLSearchParams, facets: readonly FacetView[],
    dropped: string[]): Pick<BrowseFilters, "specs" | "ranges"> {
  const specs: Record<string, string[]> = {};
  const ranges: Record<string, Range> = {};
  for (const [key, value] of params) {
    if (FIXED_KEYS.includes(key)) continue;
    const bound = BOUNDS.find((b) => key.endsWith(`_${b}`));
    const ranged = bound && facets.find((f) => f.kind === "number" && `${f.spec_key}_${bound}` === key);
    if (bound && ranged) {
      const number = boundOf(value);
      if (number === null) dropped.push(`${key}=${value}`);
      else ranges[ranged.spec_key] = { ...ranges[ranged.spec_key], [bound]: number };
      continue;
    }
    const facet = facets.find((f) => f.spec_key === key);
    const known = value.split(",").filter((id) => facet?.options.some((o) => o.id === id));
    dropped.push(...value.split(",").filter((id) => !known.includes(id)).map((id) => `${key}=${id}`));
    if (known.length > 0) specs[key] = [...new Set(known)].sort();
  }
  return { specs, ranges };
}

export const defaultSort = (q: string): BrowseSort => (q ? "relevance" : "name");

export const browseQuery = (filters: Partial<BrowseFilters>): string =>
  encodeFilters({ ...NO_FILTERS, sort: defaultSort(filters.q ?? ""), ...filters });

function decodeSort(value: string | null, q: string, columns: readonly string[],
    dropped: string[]): Pick<BrowseFilters, "sort" | "column"> {
  const fallback = { sort: defaultSort(q), column: null };
  if (value === null) return fallback;
  const sort = SORTS.find((s) => s === value && (s !== "relevance" || q));
  if (sort) return { sort, column: null };
  const key = value.endsWith("-desc") ? value.slice(0, -"-desc".length) : value;
  if (columns.includes(key)) return { ...fallback, column: { key, desc: key !== value } };
  dropped.push(`sort=${value}`);
  return fallback;
}

export function decodeFilters(query: string, vocab: FilterVocabulary): { filters: BrowseFilters; dropped: string[] } {
  const params = new URLSearchParams(query);
  const dropped: string[] = [];
  const pick = <T extends string>(key: string, allowed: (value: string) => value is T): T | null => {
    const value = params.get(key);
    if (value === null) return null;
    if (allowed(value)) return value;
    dropped.push(`${key}=${value}`);
    return null;
  };

  const category = pick("category", (v): v is string => vocab.categories.some((c) => c.id === v));
  const domain = pick("domain", (v): v is string => vocab.categories.some((c) => c.domain === v));
  const stage = pick("stage", (v): v is string => vocab.stages.includes(v));
  const page = pick("page", (v): v is string => /^[1-9]\d*$/.test(v));
  const columns = vocab.categories.find((c) => c.id === category)?.core ?? [];
  const layout = pick("view", (v): v is "table" => category !== null && v === "table") ?? "cards";
  const q = (params.get("q") ?? "").trim();
  const { sort, column } = decodeSort(params.get("sort"), q, columns, dropped);
  const { specs, ranges } = decodeFacets(params, category ? vocab.facets : [], dropped);
  return { filters: { q, category, domain, stage, specs, ranges, sort, column, layout, page: page ? Number(page) : 1 },
    dropped };
}
