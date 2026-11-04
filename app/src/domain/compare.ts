import type { ProductView, SpecCell, SpecLabel } from "./views.ts";
import { endsOf } from "./filtering/filter.ts";

export const MAX_COMPARED = 3;

export function compareQuery(ids: readonly string[], onlyDifferences: boolean): string {
  return [ids.length > 0 ? `ids=${ids.map(encodeURIComponent).join(",")}` : "",
    onlyDifferences ? "diff=1" : ""].filter(Boolean).join("&");
}

export const showsOnlyDifferences = (query: string): boolean => new URLSearchParams(query).get("diff") === "1";

interface CompareRow {
  readonly key: string;
  readonly equal: boolean;
}

interface CompareGroup {
  readonly section: "core" | "detail";
  readonly rows: readonly CompareRow[];
}

export function cellOf(product: ProductView, key: string): SpecCell {
  return [...product.core, ...product.detail].find((c) => c.key === key) ?? { key };
}

const valueOf = (product: ProductView, key: string): string => JSON.stringify(cellOf(product, key).value ?? null);

export function allEqual(products: readonly ProductView[], value: (product: ProductView) => string): boolean {
  return products.length > 1 && products.every((p) => value(p) === value(products[0]));
}

export function compareGroups(products: readonly ProductView[],
    specDefs: Readonly<Record<string, SpecLabel>>): CompareGroup[] {
  const shown = new Set<string>();
  return (["core", "detail"] as const).map((section) => {
    const keys: string[] = [];
    for (const key of products.flatMap((p) => p[section].map((c) => c.key))) {
      if (shown.has(key) || !(key in specDefs) || !products.some((p) => cellOf(p, key).value !== undefined)) continue;
      shown.add(key);
      keys.push(key);
    }
    return { section, rows: keys.map((key) => ({ key, equal: allEqual(products, (p) => valueOf(p, key)) })) };
  });
}

export function leaders(products: readonly ProductView[], key: string,
    better: SpecLabel["better"]): ReadonlySet<string> {
  if (better === undefined) return new Set();
  const scored = products.flatMap((p) => {
    const ends = endsOf(cellOf(p, key).value);
    return ends === undefined ? [] : [{ id: p.id, n: better === "higher" ? ends[1] : ends[0] }];
  });
  const top = (better === "higher" ? Math.max : Math.min)(...scored.map((s) => s.n));
  return scored.length < 2 || scored.every((s) => s.n === top) ? new Set()
    : new Set(scored.filter((s) => s.n === top).map((s) => s.id));
}
