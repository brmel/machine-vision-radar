import type { ProductCard, ViewValue } from "../views.ts";
import type { Range } from "./filterUrl.ts";

export function extractSpecOptionIds(val: ViewValue | undefined): string[] {
  if (val === undefined || "none" in val) return [];
  if ("terms" in val) return val.terms.map((t) => t.id.toLowerCase());
  if ("term" in val) return [val.term.id.toLowerCase()];
  if ("boolean" in val) return [val.boolean ? "true" : "false"];
  if ("string" in val) return [val.string.toLowerCase()];
  if ("range" in val) return [`${val.range.min}–${val.range.max}`];
  return [String(val.quantity.value)];
}

export function endsOf(val: ViewValue | undefined): readonly [number, number] | undefined {
  if (val !== undefined && "quantity" in val) return [val.quantity.value, val.quantity.value];
  return val !== undefined && "range" in val ? [val.range.min, val.range.max] : undefined;
}

export function overlaps(val: ViewValue | undefined, range: Range): boolean {
  const ends = endsOf(val);
  if (ends === undefined) return false;
  const [low, high] = ends;
  return (range.min === undefined || high >= range.min) && (range.max === undefined || low <= range.max);
}

export function offersAny(val: ViewValue | undefined, selected: readonly string[]): boolean {
  if (val === undefined) return false;
  const offered = extractSpecOptionIds(val);
  return selected.length === 0 || selected.some((v) => offered.includes(v.toLowerCase()));
}

function sortKey(val: ViewValue | undefined): number | string | undefined {
  if (val === undefined || "none" in val) return undefined;
  if ("boolean" in val) return val.boolean ? 1 : 0;
  if ("string" in val) return val.string.toLowerCase();
  if ("term" in val) return val.term.id;
  if ("terms" in val) return val.terms.map((t) => t.id).join(",");
  return endsOf(val)?.[0];
}

export function byColumn(column: { readonly key: string; readonly desc: boolean }): (a: ProductCard, b: ProductCard) =>
  number {
  return (a, b) => {
    const [x, y] = [sortKey(a.specs[column.key]), sortKey(b.specs[column.key])];
    if (x === undefined || y === undefined) return x === y ? 0 : x === undefined ? 1 : -1;
    const order = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    return column.desc ? -order : order;
  };
}
