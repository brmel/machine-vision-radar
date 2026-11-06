import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect } from "@playwright/test";
import { PAGE_SIZE } from "../../../src/domain/ports/CatalogRepository.ts";
import { radar, readView, rows, watchReads } from "../../fixture.ts";
import { inEachLocale, MESSAGES } from "../../messages.ts";
import { test } from "./admin.ts";

const FIXTURE = process.env.MVR_E2E_FIXTURE ?? "";

interface Row { id: string; slug: string; category: string; subject: string;
  value: { quantity?: { value: number } } & string; source_refs: string[]; is_primary?: boolean }

const products = rows<Row>("products.jsonl");
const names = new Map(rows<Row>("names.jsonl").filter((n) => n.is_primary).map((n) => [n.subject, n.value]));
const category = products[0]?.category ?? "";
const cards = readView<{ products: { vendor: string }[] }>("index.json").products;
const maker = [...new Set(cards.map((c) => c.vendor))].sort((a, b) => cards.filter((c) => c.vendor === b)
  .length - cards.filter((c) => c.vendor === a).length)[0];
const first =
  [...products].sort((a, b) => names.get(a.id)!.toLowerCase().localeCompare(names.get(b.id)!.toLowerCase()))[0];
const claim = rows<Row>("claims.jsonl").find((c) => c.subject === first.id && c.value.quantity?.value !== undefined)!;
inEachLocale("Firestore read model", (locale) => {
  const T = MESSAGES[locale];
  const counted = (n: number) => T.productCountOther.replace("{count}", String(n));

  test("a category page reads its facet doc and one listing page, the next page one more, no response a whole "
    + "catalog", async ({ page }) => {
    const seen = watchReads(page);
    await page.goto(`/browse?category=${encodeURIComponent(category)}`);
    await expect(page.getByRole("status")).toHaveText(counted(products.length));
    await expect(page.getByRole("main").getByRole("article")).toHaveCount(PAGE_SIZE);
    await page.waitForLoadState("networkidle");
    expect(seen.reads.sort())
      .toEqual([`/public_facets/${category}`, `/public_facets/${category}/pages/1`, "/public_index/news"]);
    await page.getByRole("button",
      { name: T.paginationPage.replace("{page}", "2").replace("{totalPages}", "2"), exact: true }).click();
    await expect(page.getByRole("main").getByRole("article")).toHaveCount(products.length - PAGE_SIZE);
    await expect(page).toHaveURL(/[?&]page=2$/);
    await expect(page.getByText(T.paginationSummary.replace("{start}", String(PAGE_SIZE + 1))
      .replace("{end}", String(products.length)).replace("{total}", String(products.length)))).toBeVisible();
    expect(seen.reads).toHaveLength(4);
    expect(seen.reads.filter((r) => /public_index\/cards|public_search/.test(r))).toEqual([]);
    expect(Math.max(...seen.listed)).toBeLessThanOrEqual(PAGE_SIZE);
  });

  test("browse without a category and a vendor page read one page of cards, never the whole "
    + "catalog", async ({ page }) => {
    const seen = watchReads(page);
    await page.goto("/browse");
    await expect(page.getByRole("status").first()).toHaveText(counted(products.length));
    await expect(page.getByRole("main").getByRole("article")).toHaveCount(PAGE_SIZE);
    await page.goto(`/vendor/${maker}`);
    await expect(page.getByRole("main").getByRole("article").first()).toBeVisible();
    await page.waitForLoadState("networkidle");
    expect(seen.reads.filter((r) => /public_index\/cards/.test(r))).toEqual([]);
    expect(seen.listed.length).toBeGreaterThan(0);
    expect(Math.max(...seen.listed)).toBeLessThanOrEqual(PAGE_SIZE);
  });

  test("after a change the product shows the new value and its History the change, after its rollback the "
    + "original", async ({ page }) => {
    const original = claim.value.quantity!.value;
    const changed = 900 + (locale === "fr" ? 1 : 0);
    const changeset = join(FIXTURE, `e2e-${locale}.json`);
    writeFileSync(changeset, JSON.stringify({ changes: [{ op: "put",
      entity: { ...claim, version: undefined, value: { quantity: { ...claim.value.quantity, value: changed } } },
      reason: "End-to-end check", actor_kind: "human", actor: "e2e", source_refs: claim.source_refs }] }));
    const opened = async (): Promise<void> => {
      await page.goto(`/browse?category=${encodeURIComponent(category)}`);
      await page.getByRole("main").getByRole("link", { name: names.get(first.id), exact: true }).click();
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(names.get(first.id)!);
    };
    radar("change", "apply", changeset);
    await opened();
    await expect(page.getByRole("main")).toContainText(String(changed));
    await page.getByRole("link", { name: T.historyLink, exact: true }).click();
    await expect(page.locator("ol.history > li").first()).toContainText("End-to-end check");
    const filed: { id: string } =
      JSON.parse(radar("--json", "record", "rollback", claim.id, "--to", "1", "--reason", "End-to-end check done"));
    radar("proposal", "approve", filed.id, "--note", "Back to the datasheet");
    await opened();
    await expect(page.getByRole("main")).toContainText(String(original));
    await expect(page.getByRole("main")).not.toContainText(String(changed));
  });
});

test("a prerendered product reads its own doc once it shows; a product opened from its listing reads one "
  + "doc", async ({ page }) => {
  const seen = watchReads(page);
  const product = products[0];
  await page.goto(`/product/${product.slug}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.waitForLoadState("networkidle");
  expect(seen.reads).toEqual([`/public_products/${product.id}`]);
  await page.goto(`/browse?category=${encodeURIComponent(category)}`);
  const card = page.getByRole("main").getByRole("article").first().getByRole("heading").getByRole("link");
  await expect(page.getByRole("main").getByRole("article")).toHaveCount(PAGE_SIZE);
  await page.waitForLoadState("networkidle");
  const before = seen.reads.length;
  await card.click();
  await expect(page).toHaveURL(/\/product\//);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(seen.reads.slice(before)).toHaveLength(1);
  expect(seen.reads.at(-1)).toMatch(/^\/public_products\/prd_|:runQuery/);
});

test("the Firestore client is its own lazy chunk", async ({ request }) => {
  const html = await (await request.get("/")).text();
  const main = html.match(/<script type="module"[^>]*src="([^"]+)"/)![1];
  const bundle = await (await request.get(main)).body();
  expect(bundle.toString()).not.toContain("runQuery");
  const lazy = [...new Set([...bundle.toString().matchAll(/firestore-[\w-]+\.js/g)].map((m) => m[0]))];
  expect(lazy).toHaveLength(1);
  expect((await (await request.get(`/assets/${lazy[0]}`)).text())).toContain("runQuery");
});
