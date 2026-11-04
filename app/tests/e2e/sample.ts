import { expect, test, type Page } from "@playwright/test";
import type { CategoryPage, FacetView, FeedItemView, FeedPageView, IndexView, LocalizedText, ProductCard,
  ProductView } from "../../src/domain/views.ts";
import { consoleErrors, readView as read } from "../fixture.ts";
import { inLocale } from "../messages.ts";

export const index = read<IndexView>("index.json");
export const news = read<FeedPageView>("news.json");
export const article = (slug: string): FeedItemView => read<FeedItemView>(`news/${slug}.json`);
export const view = (id: string): ProductView => read<ProductView>(`products/${id}.json`);
export const productViews = index.products.map((p) => view(p.id));
export const facetsOf = (category: string): readonly FacetView[] =>
  index.categories.find((c) => c.id === category)?.pages ? read<CategoryPage>(`categories/${category}/1.json`)
    .facets : [];

export const cardsOf = (category: string): ProductCard[] =>
  Array.from({ length: index.categories.find((c) => c.id === category)?.pages ?? 0 },
    (_, n) => read<CategoryPage>(`categories/${category}/${n + 1}.json`).products).flat();

export const label = (text: LocalizedText, locale: "en" | "fr"): string => (locale === "fr" && text.fr) || text.en;
const withUnit = (text: LocalizedText, unit: string | undefined, locale: "en" | "fr"): string =>
  (unit ? `${label(text, locale)} (${unit})` : label(text, locale));
export const facetLabel = (facet: FacetView, locale: "en" | "fr"): string => withUnit(facet.label, facet.unit, locale);
export const specLabel = (key: string, locale: "en" | "fr"): string =>
  withUnit(index.spec_definitions[key].label, index.spec_definitions[key].unit, locale);
export const escape = (text: string): string => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const members = (id: string) => index.products.filter((p) => p.category === id);
const choices = (id: string) => facetsOf(id)
  .filter((f) => (f.kind === "enum" || f.kind === "multi") && f.options.length >= 2);

const found = index.categories.find(
  (c) => members(c.id).length >= 2 && c.pipeline.length > 0 && choices(c.id).length >= 2 && facetsOf(c.id)
    .some((f) => f.kind === "number" && f.options.length > 0),
);
if (!found) throw new Error("no category with two products, a stage, two choice facets and a number facet");
export const category = found;
const [product, otherProduct] = members(category.id);
export const choiceFacets = choices(category.id);
export const numberFacet = facetsOf(category.id).filter((f) => f.kind === "number" && f.options.length > 0)[0];
export const word = product.name.split(/\s+/).find((w) => w.length >= 4) ?? product.name;

const recorded = index.products.find((p) => view(p.id).history);
const unrecorded = index.products.find((p) => !view(p.id).history);
const idle = index.organizations.find((o) => !index.products.some((p) => p.vendor === o.slug));
const quiet =
  index.domains.find((d) => index.categories.filter((c) => c.domain === d.id).every((c) => c.products === 0));
const titled = (p: ProductView) => Math.max(0, ...p.sources.filter((s) => s.url).map((s) => s.title?.length ?? 0));
const sourced = productViews.reduce((a, b) => (titled(b) > titled(a) ? b : a));
if (!recorded || !unrecorded || !idle || !quiet)
  throw new Error("no product with history, product without, organization without products, or domain without "
    + "products");

export const PAGES = {
  browse: `/browse?category=${category.id}`,
  search: `/browse?q=${encodeURIComponent(word)}`,
  ask: "/search",
  product: `/product/${product.slug}`,
  history: `/product/${recorded.slug}/history`,
  sources: `/product/${sourced.slug}`,
  vendor: `/vendor/${product.vendor}`,
  compare: `/compare?ids=${product.id},${otherProduct.id}`,
  news: "/news",
  article: `/news/${news.items[0].slug}`,
} as const;

export const EMPTY = {
  browse: `/browse?domain=${quiet.id}`,
  search: "/browse?q=zzqxv",
  product: "/product/no-such-product",
  history: `/product/${unrecorded.slug}/history`,
  vendor: `/vendor/${idle.slug}`,
  compare: "/compare",
  news: "/news?kind=no-such-kind",
  article: "/news/no-such-article",
} as const;

export const VIEWS = [
  ["home", "/"], ["browse", PAGES.browse], ["search", PAGES.search], ["ask", PAGES.ask], ["product", PAGES.product],
  ["history", PAGES.history], ["vendor", PAGES.vendor], ["compare", PAGES.compare], ["news", PAGES.news],
  ["article", PAGES.article], ["market", "/market"], ["about", "/about"], ["terms", "/terms"], ["privacy", "/privacy"],
  ["404", "/no-such-page"],
] as const;

export const quietTest = test.extend<{ quiet: void }>({
  quiet: [async ({ page }, use) => { const errors = consoleErrors(page); await use(); expect(errors).toEqual([]); },
    { auto: true }],
});

export async function show(page: Page, path: string, locale: string, theme: "light" | "dark" = "light"): Promise<void> {
  await inLocale(page, locale, theme);
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.waitForFunction(() => document.getAnimations()
    .every((a) => a.playState !== "running" || a.effect?.getComputedTiming().iterations === Infinity));
}
