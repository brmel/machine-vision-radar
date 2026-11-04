import { readFileSync } from "node:fs";
import { expect } from "@playwright/test";
import { index, label, productViews, quietTest as test } from "../sample.ts";
import { inEachLocale } from "../../messages.ts";

const APP_VERSION =
  (JSON.parse(readFileSync(new URL("../../../package.json", import.meta.url), "utf8")) as { version: string }).version;

const SOURCED = productViews.find((v) => v.status?.source && v.core.some((c) => c.value));
if (!SOURCED) throw new Error("no product with a sourced status and a value");
const VALUED = SOURCED.core.find((c) => c.value)?.key ?? "";
const OPAQUE_ID = /\b(src|prd|clm|org|doc)_[0-9a-z]{10}\b/;
const ISO_DATE = /\b\d{4}-\d{2}-\d{2}(T[\d:.]+Z)?\b/;

const T = {
  en: { chip: /^(Vendor website|Datasheet|Unclassified source) · \d{1,2} [A-Z][a-z]{2} 2026/, status: "Active" },
  fr: { chip: /^(Site du fabricant|Fiche technique|Source non classée) · \d{1,2} [a-zéû]{3,5}\.? 2026/,
    status: "Actif" },
} as const;

inEachLocale("Catalog honesty", (locale) => {
  const t = T[locale];
  test("each spec value shows its current source as a dated chip that links out", async ({ page }) => {
    await page.goto(`/product/${SOURCED.slug}`);
    const row = page.locator("table.spec-table tbody tr")
      .filter({ hasText: label(index.spec_definitions[VALUED].label, locale) });
    const chip = row.locator("a.source-chip");
    await expect(chip).toHaveCount(1);
    await expect(chip).toHaveText(t.chip);
    await expect(chip).toHaveAttribute("href", /^https?:\/\//);
    await expect(chip).toHaveAttribute("target", "_blank");
    const table = (await page.locator("table.spec-table").allInnerTexts()).join("\n");
    expect(table).not.toMatch(OPAQUE_ID);
    expect(table).not.toMatch(ISO_DATE);
    await expect(page.locator(".status-line")).toContainText(t.status);
    await expect(page.locator(".status-line a.source-chip")).toHaveText(t.chip);
    await expect(page.locator(".status-line")).not.toContainText(/\bper\b|\bselon\b/);
  });

  test("the Sources tab lists exactly the sources the chips point to", async ({ page }) => {
    await page.goto(`/product/${SOURCED.slug}`);
    await expect(page.locator("table.spec-table a.source-chip").first()).toBeVisible();
    const chipIds = new Set(await page.locator("a.source-chip")
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-source-id"))));
    await page.locator("main").getByRole("button", { name: /Sources/ }).first().click();
    const rows = page.locator("table.sources-table tbody tr");
    await expect(rows.first()).toBeVisible();
    const rowIds = new Set(await rows.evaluateAll((els) => els.map((e) => e.getAttribute("id"))));
    expect(rowIds).toEqual(chipIds);
    const text = await page.locator("table.sources-table").innerText();
    expect(text).not.toMatch(OPAQUE_ID);
    expect(text).not.toMatch(ISO_DATE);
    expect(text).not.toMatch(/verif|vérifi/i);
  });

  test("the footer shows one version label and no file name", async ({ page }) => {
    await page.goto("/");
    const footer = page.locator("footer");
    await expect(footer).toContainText(`Version ${APP_VERSION}`);
    const text = await footer.innerText();
    expect(text.match(/\bv(ersion)?\s?\d+\.\d+/gi)).toHaveLength(1);
    expect(text).not.toMatch(/\.json\b/);
  });
});
