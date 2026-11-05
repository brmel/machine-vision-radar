import fs from "node:fs";
import path from "node:path";
import { BRAND_CONFIG } from "../../src/ui/theme/brand.ts";
import { buildHomeHeadMeta, buildStaticHeadMeta, buildVendorHeadMeta } from "../../src/shell/seo/seo.ts";
import { buildHubHeadMeta, categoryHub } from "../../src/shell/seo/hubs.ts";
import { STATIC_ROUTES, routeFromPath } from "../../src/shell/routing/router.ts";
import { categoryPath, historyPath, productPath, vendorPath } from "../../src/domain/paths.ts";
import type { CategoryEntry } from "../../src/domain/views.ts";
import { renderNotFoundHead } from "../head.ts";
import { Sitemap, robots } from "../sitemap.ts";
import { logger } from "../../src/shell/logger.ts";
import { DEFAULT_MESSAGES } from "../../src/shell/i18n/messages.ts";
import { inEveryLanguage } from "./language.ts";
import { prerenderNews } from "./news.ts";
import { ProductRenderers } from "./pool.ts";
import { DIST_DIR, ROOT, type Site, openSite, write, writePage } from "./site.ts";
import type { ProductPages } from "./worker.ts";

const TEMPLATE_FILE = path.resolve(DIST_DIR, "index.html");

const ORGANIZATIONS_AT_ONCE = 100;

interface Listed {
  readonly category: CategoryEntry;
  readonly products: readonly ProductPages[];
}

interface Hubs {
  readonly dates: Map<string, string[]>;
  readonly pages: { readonly id: string; readonly path: string }[];
}

async function categoryPages(site: Site, renderers: ProductRenderers, category: CategoryEntry): Promise<Listed> {
  const first = await site.repo.categoryPage(category.id);
  writePage(site, `category/${category.id}.html`, buildHubHeadMeta(categoryHub(category, first.products), site.base),
    await site.render({ name: "category", category: category.id, query: "" }));
  let pages = Promise.resolve<ProductPages[][]>([]);
  for (let listing = first; ; listing = await site.repo.categoryPage(category.id, listing.next)) {
    const page = renderers.pages(listing.products.map((card) => card.id));
    pages = Promise.all([pages, page]).then(([done, last]) => [...done, last]);
    if (!listing.next) break;
  }
  return { category, products: (await pages).flat() };
}

function dateHubs(hubs: Hubs, product: ProductPages, modified: string): void {
  for (const id of [...(product.hub ? [product.id] : []), ...product.components])
    hubs.dates.set(id, [...(hubs.dates.get(id) ?? []), modified]);
}

function categorySitemap(sitemap: Sitemap, { category, products }: Listed, hubs: Hubs): number {
  const dates: string[] = [];
  for (const product of products) {
    if (product.indexable) sitemap.add({ path: productPath(product.slug), lastmod: product.modified });
    if (product.hub) hubs.pages.push({ id: product.id, path: product.hub });
    if (product.modified) {
      dates.push(product.modified);
      dateHubs(hubs, product, product.modified);
    }
    if (product.history && product.indexable) sitemap.add({ path: historyPath(product.slug) });
  }
  sitemap.add({ path: categoryPath(category.id), lastmod: dates.sort().at(-1) });
  return products.reduce((n, p) => n + (p.history ? 2 : 1) + (p.hub ? 1 : 0), 1);
}

async function vendorPages(site: Site, sitemap: Sitemap): Promise<number> {
  const slugs = (await site.repo.organizations()).map((org) => org.slug);
  for (let start = 0; start < slugs.length; start += ORGANIZATIONS_AT_ONCE) {
    const vendors = await site.repo.organizationViews(slugs.slice(start, start + ORGANIZATIONS_AT_ONCE));
    await Promise.all(vendors.map(async (vendor) => writePage(site, `vendor/${vendor.slug}.html`,
      buildVendorHeadMeta({ ...vendor, summary: vendor.summary?.en ?? "" }, site.base),
      await site.render({ name: "vendor-detail", vendorSlug: vendor.slug, page: 1 }))));
    for (const vendor of vendors) sitemap.add({ path: vendorPath(vendor.slug) });
  }
  return slugs.length;
}

async function fixedPages(site: Site): Promise<number> {
  for (const route of STATIC_ROUTES) {
    const head = buildStaticHeadMeta(`${site.base}${route.path}`, site.base, DEFAULT_MESSAGES[route.title],
      DEFAULT_MESSAGES[route.description]);
    writePage(site, route.file, head, await site.render(routeFromPath(route.path, "")));
  }
  const admin = process.env.VITE_ENABLE_ADMIN === "true";
  if (admin) write("admin.html", renderNotFoundHead(site.template,
    `${inEveryLanguage("navAdmin")} · ${BRAND_CONFIG.wordmark}`, BRAND_CONFIG.tagline));
  const notFoundHead =
    renderNotFoundHead(site.template, `${inEveryLanguage("notFoundTitle")} · ${BRAND_CONFIG.wordmark}`,
      `${inEveryLanguage("notFoundTitle")} — ${BRAND_CONFIG.tagline}`);
  const notFound = await site.render({ name: "not-found", path: "" });
  write("404.html", notFoundHead.replace(ROOT, () => `<div id="root">${notFound}</div>`));
  const { counts } = site.registry;
  writePage(site, "index.html", buildHomeHeadMeta(site.base,
    `Catalog of ${counts.products} products from ${counts.organizations} vendors in `
      + `${counts.categories} categories, compiled from public sources.`),
    await site.render({ name: "home" }));
  return STATIC_ROUTES.length + (admin ? 3 : 2);
}

async function prerender(): Promise<void> {
  if (!fs.existsSync(TEMPLATE_FILE)) {
    logger.error("prerender: missing build artifacts. Run vite build first.");
    process.exit(1);
  }
  const startTime = Date.now();
  const template = fs.readFileSync(TEMPLATE_FILE, "utf-8");
  if (!template.includes(ROOT)) throw new Error(`prerender: ${TEMPLATE_FILE} has no empty root; run vite build first`);
  const site = await openSite(template);
  const sitemap = new Sitemap(DIST_DIR, site.base);
  fs.rmSync(path.join(DIST_DIR, "read-model"), { recursive: true, force: true });
  write("read-model/registry.json", JSON.stringify(site.registry));
  write("read-model/organizations.json", JSON.stringify(await site.repo.organizations()));
  write("robots.txt", robots(site.base));
  for (const route of [{ path: "/" }, ...STATIC_ROUTES]) sitemap.add({ path: route.path });

  const renderers = new ProductRenderers(template);
  const listed = await Promise.all(site.registry.categories.filter((c) => c.products > 0)
    .map((category) => categoryPages(site, renderers, category)));
  await renderers.close();
  const hubs: Hubs = { dates: new Map(), pages: [] };
  let renderedCount = listed.reduce((n, category) => n + categorySitemap(sitemap, category, hubs), 0);
  for (const hub of hubs.pages) sitemap.add({ path: hub.path, lastmod: (hubs.dates.get(hub.id) ?? []).sort().at(-1) });
  renderedCount += await vendorPages(site, sitemap);
  renderedCount += await prerenderNews(site.repo, site.base, site.registry.data_as_of, {
    page: async (file, head, route) => writePage(site, file, head, await site.render(route)),
    file: write,
    sitemap,
  });
  renderedCount += await fixedPages(site);

  const sitemapFiles = sitemap.close();
  logger.info(`prerender: emitted ${renderedCount} static HTML pages and a sitemap index of ${sitemapFiles.length} `
    + `file(s) in ${Date.now() - startTime}ms`);
}

prerender().catch((err: unknown) => {
  logger.error("prerender failed", {}, err);
  process.exit(1);
});
