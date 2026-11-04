import type { CategoryEntry as CatalogCategory } from "../views.ts";
import { defaultSort, NO_FILTERS, type BrowseFilters, type BrowseLayout, type BrowseSort,
  type Range } from "./filterUrl.ts";

export function withCategory(f: BrowseFilters, categoryId: string | null,
    categories: readonly CatalogCategory[]): BrowseFilters {
  const cat = categories.find((c) => c.id === categoryId);
  return {
    ...f,
    category: categoryId,
    domain: cat && f.domain && f.domain !== cat.domain ? cat.domain : f.domain,
    stage: cat && f.stage && !cat.pipeline.includes(f.stage) ? null : f.stage,
    specs: {},
    ranges: {},
    column: null,
    layout: categoryId ? f.layout : "cards",
    page: 1,
  };
}

function keepCategoryIf(f: BrowseFilters, categories: readonly CatalogCategory[],
    keep: (cat: CatalogCategory) => boolean): BrowseFilters {
  const cat = categories.find((c) => c.id === f.category);
  return cat && !keep(cat) ? { ...f, category: null, specs: {}, ranges: {}, column: null, layout: "cards" } : f;
}

export function withDomain(f: BrowseFilters, domain: string | null,
    categories: readonly CatalogCategory[]): BrowseFilters {
  const next = { ...f, domain, page: 1 };
  return domain ? keepCategoryIf(next, categories, (c) => c.domain === domain) : next;
}

export function withStage(f: BrowseFilters, stage: string | null,
    categories: readonly CatalogCategory[]): BrowseFilters {
  const next = { ...f, stage, page: 1 };
  return stage ? keepCategoryIf(next, categories, (c) => c.pipeline.includes(stage)) : next;
}

export function toggleOption(f: BrowseFilters, specKey: string, optionId: string): BrowseFilters {
  const selected = f.specs[specKey] ?? [];
  const values = selected.includes(optionId) ? selected.filter((v) => v !== optionId) : [...selected, optionId].sort();
  const specs = { ...f.specs, [specKey]: values };
  if (values.length === 0) delete specs[specKey];
  return { ...f, specs, page: 1 };
}

export function withoutSpec(f: BrowseFilters, specKey: string): BrowseFilters {
  const specs = { ...f.specs };
  delete specs[specKey];
  return { ...f, specs, page: 1 };
}

export function withRange(f: BrowseFilters, specKey: string, range: Range): BrowseFilters {
  const kept: Range = { ...(range.min === undefined ? {} : { min: range.min }),
    ...(range.max === undefined ? {} : { max: range.max }) };
  const ranges = { ...f.ranges, [specKey]: kept };
  if (kept.min === undefined && kept.max === undefined) delete ranges[specKey];
  return { ...f, ranges, page: 1 };
}

export function withoutFilters(f: BrowseFilters): BrowseFilters {
  return { ...NO_FILTERS, q: f.q, sort: f.sort };
}

export const withQuery = (f: BrowseFilters, q: string): BrowseFilters =>
  ({ ...f, q, sort: defaultSort(q), column: null, page: 1 });

export const withSort = (f: BrowseFilters, sort: BrowseSort): BrowseFilters => ({ ...f, sort, column: null, page: 1 });

export const withColumn = (f: BrowseFilters, key: string): BrowseFilters =>
  ({ ...f, column: { key, desc: f.column?.key === key && !f.column.desc }, page: 1 });

export const withLayout = (f: BrowseFilters, layout: BrowseLayout): BrowseFilters => ({ ...f, layout });
export const withPage = (f: BrowseFilters, page: number): BrowseFilters => ({ ...f, page });
