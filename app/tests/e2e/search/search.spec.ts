import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DEV } from "../../../scripts/head.ts";
import { test, expect, type Page } from "@playwright/test";
import { MESSAGES, inEachLocale } from "../../messages.ts";
import { PAGE_SIZE } from "../../../src/domain/ports/CatalogRepository.ts";
import { radar, watchReads } from "../../fixture.ts";
import { category, index, label, productViews, word } from "../sample.ts";
import { metrics } from "./metrics.ts";

const LIMIT = 10;
const GLOSSY = index.products.find((p) => p.summary?.en.includes("glossy"));
const BY_MEANING = "a shiny polished gadget";
if (!GLOSSY) throw new Error("no fixture product with a glossy summary");
const ALIASES = new Map<string, string[]>();
for (const v of productViews) for (const alias of v.aliases ?? [])
  ALIASES.set(alias, [...(ALIASES.get(alias) ?? []), v.slug]);

// Justification (typed boundary): the fixture's registry copy; only its specs' aliases are read.
const SPEC_ALIAS =
  (JSON.parse(readFileSync(join(DEV, "radar/tests/fixtures/fixture_category.json"),
    "utf8")) as { registry: { "spec_definitions.json": { aliases?: string[] }[] } })
  .registry["spec_definitions.json"].flatMap((s) => s.aliases ?? [])[0];

function radarSearch(query: string): string[] {
  // Justification (typed boundary): `radar product search --json` prints its hits; only the slugs are compared.
  return (JSON.parse(radar("product", "search", query, "--limit", String(LIMIT), "--json")) as { slug: string }[])
    .map((h) => h.slug);
}

const box = (page: Page) => page.getByRole("main").getByRole("textbox").first();
const param = (page: Page, key: string) => new URL(page.url()).searchParams.get(key);

async function results(page: Page): Promise<string[]> {
  const links = page.getByRole("main").getByRole("article").getByRole("heading").getByRole("link");
  return (await links.evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? "")))
    .map((h) => h.replace(/^\/product\//, ""));
}

inEachLocale("Search", (locale) => {
  test("the catalogue ranks like `radar product search` on the same index", async ({ page }) => {
    const queries = [index.products[0].name, index.products[0].vendor_name,
      ...index.categories.filter((c) => c.products).map((c) => label(c.label, locale)), "glossy finish",
      "finition brillante", "widget long reach", SPEC_ALIAS];
    for (const query of queries) {
      const expected = radarSearch(query);
      expect(expected.length, query).toBeGreaterThan(0);
      await page.goto(`/browse?q=${encodeURIComponent(query)}`);
      await expect.poll(async () => (await results(page)).slice(0, LIMIT), { message: query }).toEqual(expected);
    }
  });

  test("a query no word matches finds a product by meaning, and says so", async ({ page }) => {
    await page.goto(`/browse?q=${encodeURIComponent(BY_MEANING)}`);
    await expect.poll(async () => (await results(page)).slice(0, 5), { timeout: 60_000 }).toContain(GLOSSY.slug);
    await expect(page.getByRole("status").first()).toContainText(MESSAGES[locale].searchClosestLabel);
  });

  test("typing searches nothing; Enter searches and keeps the words in the URL; clearing the box lists every product "
    + "again", async ({ page }) => {
    await page.goto("/browse");
    await expect(page.getByRole("main").getByRole("article").first()).toBeVisible();
    const before = await results(page);
    await box(page).fill(GLOSSY.name);
    await page.waitForLoadState("networkidle");
    expect(param(page, "q")).toBeNull();
    expect(await results(page)).toEqual(before);
    await box(page).press("Enter");
    await expect.poll(() => param(page, "q")).toBe(GLOSSY.name);
    await expect.poll(async () => (await results(page))[0]).toBe(GLOSSY.slug);
    await page.getByRole("button", { name: MESSAGES[locale].ariaClearInput }).click();
    await expect.poll(() => param(page, "q")).toBeNull();
    await expect.poll(() => results(page)).toEqual(before);
  });

  test("when the search fails the page says so and offers a retry, reading no more than one listing "
    + "page", async ({ page }) => {
    const seen = watchReads(page);
    await page.route("**/api/find", (route) => route.abort("connectionrefused"));
    await page.goto(`/browse?q=${encodeURIComponent(GLOSSY.name)}`);
    await expect(page.getByRole("heading", { name: MESSAGES[locale].searchErrorTitle })).toBeVisible();
    await page.getByRole("navigation").getByRole("link", { name: MESSAGES[locale].navBrowse, exact: true }).click();
    await expect(page.getByRole("main").getByRole("article").first()).toBeVisible();
    await page.waitForLoadState("networkidle");
    expect(Math.max(0, ...seen.listed)).toBeLessThanOrEqual(PAGE_SIZE);
  });

  test("a visit from an AI assistant is counted once, however many searches it makes", async ({ page }) => {
    const [assistant, counter] = locale === "en" ? ["https://chatgpt.com/", "from_chatgpt"]
      : ["https://www.perplexity.ai/", "from_perplexity"];
    const before = await metrics();
    const sent: unknown[] = [];
    page.on("request", (req) => {
      if (req.url().endsWith("/api/count")) sent.push(req.postDataJSON());
    });
    await page.goto(`/browse?q=${encodeURIComponent(GLOSSY.name)}`, { referer: assistant });
    await expect.poll(() => sent.length).toBeGreaterThan(0);
    await box(page).fill("zzqxv");
    await box(page).press("Enter");
    await expect.poll(() => sent.length).toBeGreaterThan(2);
    expect(sent.filter((body) => typeof body === "object" && body !== null && "from" in body))
      .toEqual([{ event: "search", from: assistant }]);
    await expect.poll(async () => (await metrics())[counter] ?? 0).toBe((before[counter] ?? 0) + 1);
  });
});

test.describe("Search", () => {
  test("an alias finds the products that carry it, as `radar product search` does", async ({ page }) => {
    expect(ALIASES.size).toBeGreaterThan(1);
    for (const [alias, slugs] of ALIASES) {
      const expected = radarSearch(alias);
      expect(slugs, alias).toContain(expected[0]);
      await page.goto(`/browse?q=${encodeURIComponent(alias)}`);
      await expect.poll(async () => (await results(page)).slice(0, LIMIT), { message: alias }).toEqual(expected);
    }
  });

  test("a search is counted server-side, with nothing of the query", async ({ page }) => {
    const before = await metrics();
    await page.goto("/browse?q=zzqxv");
    await expect(page.getByRole("status").first()).toHaveText(/^0\b/);
    await expect.poll(async () => (await metrics()).zero_result ?? 0).toBeGreaterThan(before.zero_result ?? 0);
    await expect.poll(async () => (await metrics()).page_view ?? 0).toBeGreaterThan(before.page_view ?? 0);
    expect(Object.keys(await metrics())
      .every((k) => /^(search|zero_result|result_click|page_view|answer|refusal|from_[a-z]+|ref_[a-z0-9_-]+)$/.test(k)))
      .toBe(true);
  });

  test("the catalogue's search words live in the URL with the filters", async ({ page, browser }) => {
    await page.goto(`/browse?category=${category.id}`);
    await expect(page.getByRole("main").getByRole("article").first()).toBeVisible();
    const all = await page.getByRole("main").getByRole("article").count();
    await box(page).fill(word);
    await box(page).press("Enter");
    await expect.poll(() => param(page, "q")).toBe(word);
    expect(new URL(page.url()).pathname).toBe(`/category/${category.id}`);
    await expect.poll(() => page.getByRole("main").getByRole("article").count()).toBeLessThanOrEqual(all);
    await expect(page.getByRole("main").getByRole("article").first()).toContainText(new RegExp(word, "i"));

    await page.reload();
    await expect(box(page)).toHaveValue(word);

    await page.getByRole("main").getByRole("article").first().getByRole("heading").getByRole("link").click();
    await expect(page).toHaveURL(/\/product\//);
    await page.goBack();
    await expect(box(page)).toHaveValue(word);
    expect(param(page, "q")).toBe(word);

    const fresh = await browser.newContext();
    const other = await fresh.newPage();
    await other.goto(`${new URL(page.url()).origin}/browse?q=${encodeURIComponent(word)}`);
    await expect(box(other)).toHaveValue(word);
    await fresh.close();
  });
});
