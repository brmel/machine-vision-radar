// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CategoryPage, IndexView, ProductCard } from "../../src/domain/views.ts";
import { browseView, listingQuery, type Listing } from "../../src/domain/filtering/browseView.ts";
import { decodeFilters, encodeFilters, NO_FILTERS, type BrowseFilters } from "../../src/domain/filtering/filterUrl.ts";
import { toggleOption, withCategory, withDomain, withStage } from "../../src/domain/filtering/filterTransitions.ts";
import { readView } from "../fixture.ts";
import { servedReader } from "../read-model.ts";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { I18nProvider } from "../../src/shell/i18n/index.tsx";
import { FacetGroup, type FacetOption } from "../../src/features/browse/facets/FacetGroup.tsx";
import { FacetSidebar } from "../../src/features/browse/facets/FacetSidebar.tsx";
import { RegistryProvider } from "../../src/ui/specs/RegistryContext.tsx";
import { Counts } from "../../src/features/browse/page/Counts.tsx";
import { DEFAULT_MESSAGES as T, fill } from "../../src/shell/i18n/messages.ts";

const index = readView<IndexView>("index.json");
const stages = index.pipeline_stages.map((s) => s.id);
const pages = (id: string): CategoryPage[] => Array.from({ length: index.categories.find((c) => c.id === id)!.pages },
  (_, n) => readView<CategoryPage>(`categories/${id}/${n + 1}.json`));

const choices = (id: string) => (index.categories.find((c) => c.id === id)!.pages ? pages(id)[0].facets : [])
  .filter((f) => f.options.length >= 2);
const category = index.categories.find((c) => c.pipeline.length > 0 && choices(c.id).length >= 2);
if (!category) throw new Error("no category with two facets of two options");
const CATEGORY = category.id;
const STAGE = category.pipeline[0];
const [A, B] = choices(CATEGORY);
const [a1, a2] = A.options.map((o) => o.id);
const b1 = B.options[0].id;
const vocab = { categories: index.categories, stages, facets: pages(CATEGORY)[0].facets };
const whole = (id: string): Listing =>
  ({ kind: "all", facets: pages(id)[0]?.facets ?? [], products: pages(id).flatMap((p) => p.products) });
const reader = servedReader();
const view = async (f: BrowseFilters) =>
  browseView(index, f, [], f.category ? whole(f.category)
    : { kind: "query", page: await reader.listing(listingQuery(f, index.categories), f.page, 20) }, 20);

describe("filter URL", () => {
  it("round-trips a selection through one readable, sorted URL", () => {
    const filters: BrowseFilters = {
      ...NO_FILTERS,
      category: CATEGORY,
      stage: STAGE,
      specs: { [A.spec_key]: [a2, a1], [B.spec_key]: [b1] },
      sort: "vendor",
      page: 2,
    };
    const lists: Record<string, string> =
      { [A.spec_key]: [a1, a2].sort().map(encodeURIComponent).join(","), [B.spec_key]: encodeURIComponent(b1) };
    const query = encodeFilters(filters);
    expect(query).toBe(
      [`category=${encodeURIComponent(CATEGORY)}`, `stage=${STAGE}`,
        ...Object.keys(lists).sort().map((k) => `${k}=${lists[k]}`), "sort=vendor", "page=2"].join("&"),
    );
    const decoded = decodeFilters(query, vocab);
    expect(decoded.dropped).toEqual([]);
    expect(decoded.filters).toEqual({ ...filters, specs: { [A.spec_key]: [a1, a2].sort(), [B.spec_key]: [b1] } });
    expect(decodeFilters(query.replace(",", "%2C"), vocab).filters).toEqual(decoded.filters);
    expect(encodeFilters(NO_FILTERS)).toBe("");
  });

  it("drops what the read model does not know and says what it dropped", () => {
    const { filters, dropped } =
      decodeFilters(`category=${CATEGORY}&${A.spec_key}=${a1},no_such_option&colour=red&stage=fly&page=0&vendor=nobody`,
        vocab);
    expect(filters).toEqual({ ...NO_FILTERS, category: CATEGORY, specs: { [A.spec_key]: [a1] } });
    expect(dropped.sort())
      .toEqual(["colour=red", `${A.spec_key}=no_such_option`, "page=0", "stage=fly", "vendor=nobody"].sort());
    expect(decodeFilters(`${A.spec_key}=${a1}`, vocab).dropped).toEqual([`${A.spec_key}=${a1}`]);
  });
});

describe("range filters", () => {
  it("read a bound from the URL with a decimal point or comma, write it with a point, and drop a bound that is not a "
    + "number", () => {
    const number = pages(CATEGORY)[0].facets.find((f) => f.kind === "number");
    if (!number) throw new Error(`no number facet in ${CATEGORY}`);
    const comma = decodeFilters(`category=${CATEGORY}&${number.spec_key}_min=3,45&${number.spec_key}_max=abc`, vocab);
    expect(comma.filters.ranges).toEqual({ [number.spec_key]: { min: 3.45 } });
    expect(comma.dropped).toEqual([`${number.spec_key}_max=abc`]);
    expect(encodeFilters(comma.filters)).toBe(`category=${encodeURIComponent(CATEGORY)}&${number.spec_key}_min=3.45`);
  });
});

describe("browse counts", () => {
  it("gives each facet option the number of results selecting it leads to", async () => {
    const start = { ...NO_FILTERS, category: CATEGORY, specs: { [A.spec_key]: [a1] } };
    const { facets, resultCount } = await view(start);
    expect(facets.length).toBeGreaterThan(1);
    for (const facet of facets.filter((x) => x.spec_key !== A.spec_key)) {
      for (const option of facet.options) {
        expect(option.count, `${facet.spec_key}=${option.id}`).toBeGreaterThan(0);
        expect((await view(toggleOption(start, facet.spec_key, option.id))).resultCount,
          `${facet.spec_key}=${option.id}`).toBe(option.count);
      }
    }
    expect(resultCount).toBeGreaterThan(0);
  });

  it("gives each domain, stage and category the number of results selecting it leads to", async () => {
    for (const start of [{ ...NO_FILTERS, stage: STAGE, category: CATEGORY }, { ...NO_FILTERS, stage: STAGE }]) {
      const v = await view(start);
      for (const [domain, n] of Object.entries(v.domainCounts))
        expect((await view(withDomain(start, domain, index.categories))).resultCount, domain).toBe(n);
      for (const [category, n] of Object.entries(v.categoryCounts))
        expect((await view(withCategory(start, category, index.categories))).resultCount, category).toBe(n);
      for (const stage of stages) expect((await view(withStage(start, stage, index.categories))).resultCount, stage)
        .toBe(v.stageCounts[stage]);
    }
  });

  it("pages 20 products at a time from the listing query and clamps a page past the end", async () => {
    const all = await view(NO_FILTERS);
    expect(all.products).toHaveLength(20);
    expect(all.totalPages).toBe(Math.ceil(index.products.length / 20));
    const last = await view({ ...NO_FILTERS, page: 999 });
    expect(last.page).toBe(all.totalPages);
    expect(last.filters.page).toBe(all.totalPages);
  });

  it("orders a whole category by name as the store does: code point on the lower-cased name, ties on the id", () => {
    const card = (id: string, name: string): ProductCard => ({ ...pages(CATEGORY)[0].products[0], id, name });
    const products = [card("prd_c", "Zeta"), card("prd_a", "élan"), card("prd_d", "Alpha"), card("prd_b", "alpha")];
    const v = browseView(index, { ...NO_FILTERS, category: CATEGORY }, [], { kind: "all", facets: [], products }, 20);
    expect(v.products.map((p) => p.id)).toEqual(["prd_b", "prd_d", "prd_c", "prd_a"]);
  });

  it("a category in name order shows the listing page the URL names, with the category's counts", () => {
    const [first, second] = pages(CATEGORY);
    const v = browseView(index, { ...NO_FILTERS, category: CATEGORY, page: 2 }, [],
      { kind: "page", page: second ?? first }, 20);
    expect(v.products).toEqual((second ?? first).products);
    expect([v.resultCount, v.totalPages]).toEqual([category.products, category.pages]);
    expect(v.facets).toEqual(first.facets);
  });
});

const options = (picked: number): FacetOption[] =>
  Array.from({ length: 12 },
    (_, i) => ({ id: `o${i}`, label: `Option ${i}`, on: i === picked, onClick: () => undefined }));

describe("a facet group", () => {
  afterEach(cleanup);

  it("shows every option, folds to eight and the picked one on demand, and filters them by name", () => {
    render(<I18nProvider><FacetGroup title="Mount" options={options(10)} onReset={() => undefined} /></I18nProvider>);
    const chips = () => within(screen.getByRole("group", { name: "Mount" })).getAllByRole("button");
    expect(chips()).toHaveLength(12);
    fireEvent.click(screen.getByRole("button", { name: "Show fewer" }));
    expect(chips().map((c) => c.getAttribute("aria-pressed"))).toEqual([...Array(8).fill("false"), "true"]);
    fireEvent.click(screen.getByRole("button", { name: "+3 more" }));
    fireEvent.change(screen.getByRole("searchbox", { name: "Filter Mount by name" }),
      { target: { value: "option 1" } });
    expect(chips().map((c) => c.textContent)).toEqual(["Option 1", "Option 10", "Option 11"]);
  });

  it("dims the unpicked while one is picked, and its reset clears the group", () => {
    const reset = vi.fn();
    render(<I18nProvider><FacetGroup title="Finish" options={options(0).slice(0, 3)} onReset={reset} /></I18nProvider>);
    const chips = within(screen.getByRole("group", { name: "Finish" })).getAllByRole("button");
    expect(chips.map((c) => c.className.includes("opacity-60"))).toEqual([false, true, true]);
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(reset).toHaveBeenCalledOnce();
  });
});

describe("the filter sidebar", () => {
  afterEach(cleanup);

  it("shows every facet of the category until the reader folds them to the first three", async () => {
    const shown = await view({ ...NO_FILTERS, category: CATEGORY });
    const facets = [...shown.facets, ...shown.facets.map((f) => ({ ...f, spec_key: `${f.spec_key}_again` }))];
    render(<I18nProvider><RegistryProvider value={index}>
      <FacetSidebar view={{ ...shown, facets }} categories={index.categories} onChange={() => undefined}
        onDone={() => undefined} className="" />
    </RegistryProvider></I18nProvider>);
    const headings = () => within(screen.getByRole("group", { name: "Specifications" })).getAllByRole("heading");
    expect(headings()).toHaveLength(facets.length);
    fireEvent.click(screen.getByRole("button", { name: "Fewer filters" }));
    expect(headings()).toHaveLength(3);
  });
});

describe("a market table", () => {
  afterEach(cleanup);

  it("shows ten rows a page, pages the rest, and names its pager after it", () => {
    const rows = Array.from({ length: 12 }, (_, n) => ({ key: `v${n}`, cells: [`Vendor ${n + 1}`, 12 - n] }));
    render(<I18nProvider>
      <Counts label="Vendors" heads={["Vendor", "Products"]} numbers={[1]} rows={rows} />
    </I18nProvider>);
    const body = () => within(screen.getByRole("table", { name: "Vendors" })).getAllByRole("row").slice(1);
    const pager = screen.getByRole("navigation", { name: fill(T.paginationTableLabel, { table: "Vendors" }) });
    expect(body().map((r) => r.textContent)).toEqual(rows.slice(0, 10).map((r) => r.cells.join("")));
    expect(pager.textContent).toContain(fill(T.paginationRows, { start: 1, end: 10, total: 12 }));
    fireEvent.click(within(pager).getByRole("button", { name: fill(T.paginationPage, { page: 2, totalPages: 2 }) }));
    expect(body().map((r) => r.textContent)).toEqual(["Vendor 112", "Vendor 121"]);
  });
});
