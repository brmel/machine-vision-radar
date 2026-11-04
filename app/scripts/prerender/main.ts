import fs from "node:fs";
import path from "node:path";
import { BRAND_CONFIG } from "../../src/ui/theme/brand.ts";
import { type PageHeadMeta, buildHomeHeadMeta, buildStaticHeadMeta, buildVendorHeadMeta,
  serializeJsonLd } from "../../src/shell/seo/seo.ts";
import { buildProductHeadMeta, productSeo } from "../../src/shell/seo/product.ts";
import { buildHubHeadMeta, categoryHub, componentHub } from "../../src/shell/seo/hubs.ts";
import { STATIC_ROUTES, routeFromPath } from "../../src/shell/routing/router.ts";
import type { Route } from "../../src/shell/routing/routes.ts";
import type { Start } from "../../src/shell/root/start.ts";
import type { RegistryLabels } from "../../src/ui/specs/RegistryContext.tsx";
import { PAGE_SIZE, type CatalogRepository } from "../../src/domain/ports/CatalogRepository.ts";
import { categoryPath, historyPath, hubPath, productPath, vendorPath } from "../../src/domain/paths.ts";
import type { CategoryEntry, ProductView, RegistryView } from "../../src/domain/views.ts";
import { readModel, renderHead, renderNotFoundHead, resolveSiteOrigin } from "../head.ts";
import { Sitemap, lastmod, robots } from "../sitemap.ts";
import { logger } from "../../src/shell/logger.ts";
import { DEFAULT_MESSAGES, DEFAULT_VALUE_LABELS } from "../../src/shell/i18n/messages.ts";
import { inEveryLanguage } from "./language.ts";
import { prerenderNews } from "./news.ts";

const SERVER = path.resolve(import.meta.dirname, "../../dist-server/server.js");
const DIST_DIR = path.resolve(process.env.MVR_PRERENDER_OUT ?? path.resolve(import.meta.dirname, "../../dist"));
const TEMPLATE_FILE = path.resolve(DIST_DIR, "index.html");

const ROOT = '<div id="root"></div>';

const ORGANIZATIONS_AT_ONCE = 100;

function write(file: string, text: string): void {
  const at = path.join(DIST_DIR, file);
  fs.mkdirSync(path.dirname(at), { recursive: true });
  fs.writeFileSync(at, text, "utf-8");
}

function writePage(template: string, file: string, head: PageHeadMeta, body: string, embedded?: ProductView): void {
  const html = renderHead(template, head).replace(ROOT, () => `<div id="root">${body}</div>`);
  write(file, embedded ? html.replace("</body>",
    () => `<script type="application/json" id="mvr-product">${serializeJsonLd(embedded)}</script>\n</body>`) : html);
}

interface Site {
  repo: CatalogRepository;
  template: string;
  base: string;
  labels: RegistryLabels;
  sitemap: Sitemap;
  render: (route: Route) => Promise<string>;
}

async function renderer(repo: CatalogRepository): Promise<Site["render"]> {
  if (!fs.existsSync(SERVER)) throw new Error(`prerender: no ${SERVER}; run npm run build:server first`);
  // Justification (typed boundary): dist-server/server.js is src/shell/root/server.tsx as vite build --ssr writes it.
  const { renderPage } = (await import(SERVER)) as typeof import("../../src/shell/root/server.tsx");
  return (route) => {
    const start: Start = { route, preferred: [], theme: "system", compared: [], prerendered: null };
    return renderPage(start, repo);
  };
}

interface Hubs {
  dates: Map<string, string[]>;
  products: ProductView[];
}

function dateHubs(hubs: Hubs, product: ProductView, modified: string): void {
  for (const id of [...(product.hub ? [product.id] : []), ...product.components.map((c) => c.id)])
    hubs.dates.set(id, [...(hubs.dates.get(id) ?? []), modified]);
}

async function productPages(site: Site, product: ProductView, hubs: Hubs): Promise<string | undefined> {
  const history = product.history ? await site.repo.history(product.id) : null;
  const seo = productSeo(product, site.labels, DEFAULT_VALUE_LABELS);
  const head = buildProductHeadMeta(seo, site.base);
  const modified = lastmod(product, history);
  writePage(site.template, `product/${product.slug}.html`, head,
    await site.render({ name: "product-detail", productId: product.id }), product);
  if (product.indexable) site.sitemap.add({ path: productPath(product.slug), lastmod: modified });
  if (product.hub) hubs.products.push(product);
  if (modified) dateHubs(hubs, product, modified);
  if (history) {
    const body = await site.render({ name: "product-history", productId: product.id });
    writePage(site.template, `product/${product.slug}/history.html`,
      { ...head, canonicalUrl: `${site.base}${historyPath(product.slug)}` }, body);
    if (product.indexable) site.sitemap.add({ path: historyPath(product.slug) });
  }
  return modified;
}

async function categoryPages(site: Site, category: CategoryEntry, hubs: Hubs): Promise<number> {
  const dates: string[] = [];
  const first = await site.repo.categoryPage(category.id);
  let written = 0;
  for (let listing = first; ; listing = await site.repo.categoryPage(category.id, listing.next)) {
    for (const product of await site.repo.products(listing.products.map((card) => card.id))) {
      const modified = await productPages(site, product, hubs);
      if (modified) dates.push(modified);
      written += product.history ? 2 : 1;
    }
    if (!listing.next) break;
  }
  const hub = categoryHub(category, first.products);
  const body = await site.render({ name: "category", category: category.id, query: "" });
  writePage(site.template, `category/${category.id}.html`, buildHubHeadMeta(hub, site.base), body);
  site.sitemap.add({ path: categoryPath(category.id), lastmod: dates.sort().at(-1) });
  return written + 1;
}

async function componentHubPages(site: Site, categories: readonly CategoryEntry[], hubs: Hubs): Promise<number> {
  for (const product of hubs.products) {
    const category = categories.find((c) => c.id === product.category);
    if (!category?.component_hub)
      throw new Error(`prerender: ${product.id} has a hub but its category names no hub path`);
    const at = hubPath(category.component_hub, product.slug);
    const { products, total } = await site.repo.listing({ uses: product.id, sort: "name" }, 1, PAGE_SIZE);
    const head = buildHubHeadMeta(componentHub(product, category, products, total), site.base);
    const body = await site.render({ name: "hub", path: category.component_hub, slug: product.id, page: 1 });
    writePage(site.template, `${at.slice(1)}.html`, head, body);
    site.sitemap.add({ path: at, lastmod: (hubs.dates.get(product.id) ?? []).sort().at(-1) });
  }
  return hubs.products.length;
}

async function vendorPages(site: Site): Promise<number> {
  const slugs = (await site.repo.organizations()).map((org) => org.slug);
  let written = 0;
  for (let start = 0; start < slugs.length; start += ORGANIZATIONS_AT_ONCE) {
    for (const vendor of await site.repo.organizationViews(slugs.slice(start, start + ORGANIZATIONS_AT_ONCE))) {
      const body = await site.render({ name: "vendor-detail", vendorSlug: vendor.slug, page: 1 });
      writePage(site.template, `vendor/${vendor.slug}.html`,
        buildVendorHeadMeta({ ...vendor, summary: vendor.summary?.en ?? "" }, site.base), body);
      site.sitemap.add({ path: vendorPath(vendor.slug) });
      written++;
    }
  }
  return written;
}

async function fixedPages(site: Site, registry: RegistryView): Promise<number> {
  for (const route of STATIC_ROUTES) {
    const head = buildStaticHeadMeta(`${site.base}${route.path}`, site.base, DEFAULT_MESSAGES[route.title],
      DEFAULT_MESSAGES[route.description]);
    writePage(site.template, route.file, head, await site.render(routeFromPath(route.path, "")));
  }
  const admin = process.env.VITE_ENABLE_ADMIN === "true";
  if (admin) write("admin.html", renderNotFoundHead(site.template,
    `${inEveryLanguage("navAdmin")} · ${BRAND_CONFIG.wordmark}`, BRAND_CONFIG.tagline));
  const notFoundHead =
    renderNotFoundHead(site.template, `${inEveryLanguage("notFoundTitle")} · ${BRAND_CONFIG.wordmark}`,
      `${inEveryLanguage("notFoundTitle")} — ${BRAND_CONFIG.tagline}`);
  const notFound = await site.render({ name: "not-found", path: "" });
  write("404.html", notFoundHead.replace(ROOT, () => `<div id="root">${notFound}</div>`));
  writePage(site.template, "index.html", buildHomeHeadMeta(site.base,
    `Catalog of ${registry.counts.products} products from ${registry.counts.organizations} vendors in `
      + `${registry.counts.categories} categories, compiled from public sources.`),
    await site.render({ name: "home" }));
  return STATIC_ROUTES.length + (admin ? 3 : 2);
}

async function prerender(): Promise<void> {
  if (!fs.existsSync(TEMPLATE_FILE)) {
    logger.error("prerender: missing build artifacts. Run vite build first.");
    process.exit(1);
  }
  const startTime = Date.now();
  const repo = readModel();
  const registry = await repo.registry();
  const base = resolveSiteOrigin();
  const template = fs.readFileSync(TEMPLATE_FILE, "utf-8");
  if (!template.includes(ROOT)) throw new Error(`prerender: ${TEMPLATE_FILE} has no empty root; run vite build first`);
  const site: Site = { repo, base, template, sitemap: new Sitemap(DIST_DIR, base), labels: registry,
    render: await renderer(repo) };
  fs.rmSync(path.join(DIST_DIR, "read-model"), { recursive: true, force: true });
  write("read-model/registry.json", JSON.stringify(registry));
  write("read-model/organizations.json", JSON.stringify(await repo.organizations()));
  write("robots.txt", robots(base));
  for (const route of [{ path: "/" }, ...STATIC_ROUTES]) site.sitemap.add({ path: route.path });

  const hubs: Hubs = { dates: new Map(), products: [] };
  let renderedCount = 0;
  for (const category of registry.categories.filter((c) => c.products > 0))
    renderedCount += await categoryPages(site, category, hubs);
  renderedCount += await componentHubPages(site, registry.categories, hubs);
  renderedCount += await vendorPages(site);
  renderedCount += await prerenderNews(repo, base, registry.data_as_of, {
    page: async (file, head, route) => writePage(site.template, file, head, await site.render(route)),
    file: write,
    sitemap: site.sitemap,
  });
  renderedCount += await fixedPages(site, registry);

  const sitemapFiles = site.sitemap.close();
  logger.info(`prerender: emitted ${renderedCount} static HTML pages and a sitemap index of ${sitemapFiles.length} `
    + `file(s) in ${Date.now() - startTime}ms`);
}

prerender().catch((err: unknown) => {
  logger.error("prerender failed", {}, err);
  process.exit(1);
});
