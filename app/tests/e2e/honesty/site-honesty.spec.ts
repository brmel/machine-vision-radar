import { resolveSiteOrigin } from "../../../scripts/head.ts";
import { test, expect, type Page } from "@playwright/test";
import { MESSAGES, inEachLocale } from "../../messages.ts";
import { bannedClaims } from "../../../studio/clips/script.ts";
import { formatCountry } from "../../../src/ui/specs/specFormat.ts";
import { BRAND_CONFIG } from "../../../src/ui/theme/brand.ts";
import { STATIC_ROUTES } from "../../../src/shell/routing/router.ts";
import { PAGES, VIEWS, category, escape, index, label, view } from "../sample.ts";

async function siteText(page: Page, root = "body"): Promise<string> {
  return page.locator(root).evaluate((el) => {
    const lines: string[] = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const parent = node.parentElement;
      const text = node.textContent?.trim();
      if (text && parent && !parent.closest("script, style, [lang]:not(html)")) lines.push(text);
    }
    return lines.join("\n");
  });
}

const FRENCH = new Map(Object.entries(MESSAGES.fr));
const ENGLISH_ONLY = Object.entries(MESSAGES.en)
  .filter(([key, en]) => en !== FRENCH.get(key) && /\p{L}/u.test(en.replace(/\{\w+\}/g, "")))
  .map(([, en]) => ({
    text: en,
    words: en.split(/\s+/).length,
    pattern: new RegExp(`(^|[^\\p{L}])${en.replace(/[.*+?^$()|[\]\\]/g, "\\$&")
      .replace(/\\?\{\w+\\?\}/g, ".+?")}($|[^\\p{L}])`, "u"),
  }));

function englishIn(text: string, minWords: number): string[] {
  return ENGLISH_ONLY.filter((s) => s.words >= minWords && s.pattern.test(text)).map((s) => s.text);
}

inEachLocale("Site honesty", (locale) => {
  test("home counts are computed from the read model", async ({ page }) => {
    const { products, organizations, categories } = index.counts;
    await page.goto("/");
    const stats = MESSAGES[locale].liveStats.replace("{products}", String(products))
      .replace("{vendors}", String(organizations)).replace("{categories}", String(categories));
    await expect(page.getByRole("main")).toContainText(stats);
  });
});

const ORIGIN = resolveSiteOrigin();
const CANONICAL: readonly string[] = ["/", "/browse", PAGES.product, PAGES.vendor, PAGES.news, PAGES.article];
const UNCODED: readonly string[] = ["/browse", PAGES.browse, PAGES.search, PAGES.product, PAGES.vendor];
const UNHEADED: readonly string[] = VIEWS.filter(([name]) => name === "404" || name === "history")
  .map(([, path]) => path);

inEachLocale("Site language", (locale) => {
  test(`every public page is in ${locale}, claims nothing the data cannot back, and keeps its canonical `
    + `origin`, async ({ page }) => {
    for (const path of [...VIEWS.map(([, p]) => p), "/browse", "/compare"]) {
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      await page.waitForLoadState("networkidle");
      const text = await siteText(page);
      expect(bannedClaims(text, locale).map((f) => `${path}: ${f}`)).toEqual([]);
      if (locale === "fr") {
        expect(englishIn(await siteText(page, "main"), 2), `${path}: English sentences in the page`).toEqual([]);
        expect(englishIn(`${await siteText(page, "header:not(main header)")}\n${await siteText(page, "footer")}`, 1),
          `${path}: English words in the header or footer`).toEqual([]);
      }
      if (UNCODED.includes(path)) {
        const main = await siteText(page, "main");
        const coded = [RAW_CODE, /\bTrue\b|\bFalse\b|\d one\b/, /VISION 20\d\d|booth|stand \w+ hall/i, ISO_DATE,
          /\b(prd|org|src|clm|doc)_[0-9a-z]{10}\b/];
        expect(coded.map((re) => main.match(re)?.[0]).filter(Boolean), path).toEqual([]);
      }
      if (CANONICAL.includes(path)) expect(await page.locator('link[rel="canonical"]').getAttribute("href"), path)
        .toBe(`${ORIGIN}${path}`);
      if (UNHEADED.includes(path)) continue;
      const head: Record<string, string | undefined> = await page.evaluate(() => {
        const content = (key: string) =>
          document.head.querySelector(`meta[name="${key}"], meta[property="${key}"]`)?.getAttribute("content")
            ?? undefined;
        const canonical = document.head.querySelector('link[rel="canonical"]')?.getAttribute("href") ?? undefined;
        return { title: document.title, description: content("description"), canonical,
          ...Object.fromEntries(["og:title", "og:description", "og:url", "og:site_name", "og:image", "twitter:card",
            "twitter:image"].map((k) => [k, content(k)])) };
      });
      const fixed = STATIC_ROUTES.find((r) => r.path === path);
      expect(head, path).toEqual({ title: fixed ? `${MESSAGES[locale][fixed.title]} — ${BRAND_CONFIG.wordmark}`
        : expect.stringContaining(BRAND_CONFIG.wordmark), description: expect.stringContaining(BRAND_CONFIG.tagline),
        canonical: expect.stringContaining(ORIGIN), "og:title": head.title, "og:description": head.description,
        "og:url": head.canonical, "og:site_name": BRAND_CONFIG.wordmark, "og:image": `${ORIGIN}/og-card.png`,
        "twitter:card": "summary_large_image", "twitter:image": `${ORIGIN}/og-card.png` });
    }
  });
});

const RAW_CODE =
  new RegExp(`\\b[a-z]+_[a-z_]+\\b|\\b(${index.domains.map((d) => escape(d.id)).join("|")})\\.[a-z_.]+\\b`);
const ISO_DATE = /\b\d{4}-\d{2}-\d{2}\b/;
const PRODUCT = view(index.products.find((p) => p.category === category.id)?.id ?? "");
const DOMAIN = index.domains.find((d) => d.id === category.domain);
const COUNTRY = index.organizations.find((o) => o.slug === PRODUCT.vendor.slug)?.country;
if (!DOMAIN || !COUNTRY) throw new Error("the sample needs a domain and a vendor with a country");

inEachLocale("Data rebuild fixes", (locale) => {
  test("breadcrumb, country and category names are in the page language (a spec row's is "
    + "product-specs')", async ({ page }) => {
    const categoryName = label(category.label, locale);
    const country = formatCountry(COUNTRY, locale);
    await page.goto(PAGES.product);
    const breadcrumb = page.getByRole("navigation", { name: MESSAGES[locale].breadcrumbLabel });
    await expect(breadcrumb).toContainText(label(DOMAIN.label, locale));
    await expect(breadcrumb).toContainText(categoryName);
    await expect(page.locator("main")).toContainText(country);
    await page.goto(PAGES.vendor);
    await expect(page.locator("main")).toContainText(country);
    await expect(page.locator("main").getByRole("article").first()).toContainText(categoryName);
    await page.goto(PAGES.search);
    await expect(page.locator("main").getByRole("article").first()).toContainText(categoryName);
  });

  test("a vendor's page names the vendor once, not on each of its cards", async ({ page }) => {
    await page.goto(PAGES.vendor);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(PRODUCT.vendor.name);
    const cards = page.locator("main").getByRole("article");
    await expect(cards.first()).toBeVisible();
    await expect(cards.filter({ hasText: PRODUCT.vendor.name })).toHaveCount(0);
  });
});
