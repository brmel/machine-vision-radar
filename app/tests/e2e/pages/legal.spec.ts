import { test, expect, type Locator } from "@playwright/test";
import { BRAND_CONFIG, type RoleAddress } from "../../../src/ui/theme/brand.ts";
import { MESSAGES, inEachLocale } from "../../messages.ts";
import { PAGES, index } from "../sample.ts";

async function expectAddresses(main: Locator, role: RoleAddress["role"]): Promise<void> {
  const set = BRAND_CONFIG.contact.filter((c) => c.role === role && c.address).map((c) => `mailto:${c.address}`);
  expect(await main.locator('a[href^="mailto:"]').evaluateAll((links) => links.map((a) => a.getAttribute("href"))))
    .toEqual(set);
}

inEachLocale("Legal pages", (locale) => {
  const t = MESSAGES[locale];
  const params = { brand: BRAND_CONFIG.wordmark, licence: BRAND_CONFIG.licence.name, report: t.reportErrorAction };
  const say = (text: string): string => Object.entries(params)
    .reduce((out, [key, value]) => out.replaceAll(`{${key}}`, value), text);

  test("the footer links About, the terms, the privacy notice and the data licence", async ({ page }) => {
    await page.goto("/");
    const footer = page.locator("footer");
    await expect(footer.getByRole("link", { name: say(t.footerLicence) }))
      .toHaveAttribute("href", BRAND_CONFIG.licence.url);
    for (const [name, path, title] of [[t.footerAbout, "/about", t.aboutTitle], [t.termsTitle, "/terms", t.termsTitle],
      [t.privacyTitle, "/privacy", t.privacyTitle]]) {
      await footer.getByRole("link", { name, exact: true }).click();
      await expect(page).toHaveURL(path);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(say(title));
    }
  });

  test("the terms give the sources and their limits, the data licence, the media rights and the way to "
    + "report", async ({ page }) => {
    await page.goto("/terms");
    const main = page.getByRole("main");
    for (const text of [t.termsSources, t.termsLicence, t.termsMedia, t.termsCorrections]) await expect(main)
      .toContainText(say(text));
    await expect(main.getByRole("link", { name: say(t.termsLicenceLink) }))
      .toHaveAttribute("href", BRAND_CONFIG.licence.url);
    await expectAddresses(main, "corrections");
  });

  test("the privacy notice says what the site sends and keeps, and the browser holds no cookie", async ({ page,
    context }) => {
    await page.goto("/privacy");
    const main = page.getByRole("main");
    for (const text of [t.privacyBrowser, t.privacyCounts, t.privacyAsk, t.privacyReport, t.privacyAdmin,
      t.privacyProviders, t.privacyRequests]) {
      await expect(main).toContainText(say(text));
    }
    await expectAddresses(main, "privacy");
    for (const path of ["/", PAGES.search, PAGES.product]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
    }
    expect(await context.cookies()).toEqual([]);
  });

  test("about names the domains and states the radar's independence", async ({ page }) => {
    await page.goto("/about");
    const main = page.getByRole("main");
    const intro = main.locator("p").first();
    for (const d of index.domains) await expect(intro).toContainText(d.label[locale] ?? d.label.en);
    await expect(intro).toContainText(String(index.domains.length));
    await expect(main.getByRole("term").filter({ hasText: t.principleIndependent })).toBeVisible();
    await expect(main.getByRole("definition").filter({ hasText: t.principleIndependentDesc })).toBeVisible();
  });
});
