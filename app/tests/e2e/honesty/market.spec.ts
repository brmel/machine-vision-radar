import { test, expect } from "@playwright/test";
import type { MarketView, RegistryView } from "../../../src/domain/views.ts";
import { categoryPath, vendorPath } from "../../../src/domain/paths.ts";
import { fill } from "../../../src/shell/i18n/messages.ts";
import { formatCountry, localized } from "../../../src/ui/specs/specFormat.ts";
import { MESSAGES, inEachLocale } from "../../messages.ts";
import { readView } from "../../fixture.ts";

const market = readView<MarketView>("market.json");
const registry = readView<RegistryView>("registry.json");

inEachLocale("The market page", (locale) => {
  const t = MESSAGES[locale];
  const country = (code?: string) => (code ? formatCountry(code, locale) : "—");
  const label = (id: string) => localized(registry.categories.find((c) => c.id === id)!.label, locale);

  test("home links the market, whose four tables state each count with its base and open a category and a vendor",
    async ({ page }) => {
      await page.goto("/");
      await page.getByRole("link", { name: t.homeMarketLink }).click();
      await expect(page).toHaveURL("/market");
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(t.marketTitle);
      const main = page.getByRole("main");
      const rows = (table: string) => main.getByRole("table", { name: table, exact: true }).locator("tbody tr");

      const products = market.categories.reduce((sum, c) => sum + c.products, 0);
      await expect(main).toContainText(fill(t.marketCategoriesBase, { products }));
      await expect(rows(t.marketCategories))
        .toHaveText(market.categories.map((c) => `${label(c.category)}${c.products}${c.vendors}`));
      await expect(main).toContainText(
        fill(t.marketVendorsBase, { vendors: market.vendors.length, organizations: market.organizations }));
      await expect(rows(t.marketVendors)).toHaveText(market.vendors.map((v) =>
        `${v.organization.name}${country(v.organization.country)}${v.products}${v.categories}`));
      const located = market.countries.reduce((sum, c) => sum + c.organizations, 0);
      await expect(main).toContainText(fill(t.marketCountriesBase, { located, organizations: market.organizations }));
      await expect(rows(t.marketCountriesTitle))
        .toHaveText(market.countries.map((c) => `${country(c.country)}${c.organizations}${c.products}`));
      await expect(main).toContainText(t.marketOwnershipBase);
      await expect(rows(t.marketOwnershipTitle)).toHaveText(market.consolidation.map((e) =>
        `${e.year ?? "—"}${e.organization.name}${localized(e.type.label, locale)}${e.owner.name}`));

      const [vendor] = market.vendors;
      await rows(t.marketVendors).getByRole("link", { name: vendor.organization.name, exact: true }).click();
      await expect(page).toHaveURL(vendorPath(vendor.organization.slug));
      await page.goBack();
      const [category] = market.categories;
      await main.getByRole("link", { name: label(category.category), exact: true }).click();
      await expect(page).toHaveURL(categoryPath(category.category));
    });

  test("on a phone, a table wider than the screen scrolls in its own frame, never the page", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/market");
    await expect(page.getByRole("main").getByRole("table").first()).toBeVisible();
    await page.addStyleTag({ content: "main table { min-width: 600px }" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  });
});
