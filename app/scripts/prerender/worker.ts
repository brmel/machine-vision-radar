import { parentPort, workerData } from "node:worker_threads";
import { buildProductHeadMeta, productSeo } from "../../src/shell/seo/product.ts";
import { buildHubHeadMeta, componentHub, familyCompare } from "../../src/shell/seo/hubs.ts";
import { PAGE_SIZE } from "../../src/domain/ports/CatalogRepository.ts";
import { historyPath, hubPath } from "../../src/domain/paths.ts";
import type { CategoryEntry } from "../../src/domain/views.ts";
import type { ProductView } from "../../src/domain/views.ts";
import { DEFAULT_VALUE_LABELS } from "../../src/shell/i18n/messages.ts";
import { lastmod } from "../sitemap.ts";
import { type Site, openSite, writePage } from "./site.ts";

export interface ProductPages {
  readonly id: string;
  readonly slug: string;
  readonly indexable: boolean;
  readonly history: boolean;
  readonly modified?: string;
  readonly hub?: string;
  readonly compared: boolean;
  readonly components: readonly string[];
}

function categoryOf(site: Site, product: ProductView): CategoryEntry {
  const category = site.registry.categories.find((c) => c.id === product.category);
  if (!category) throw new Error(`prerender: ${product.id} is in no category of the registry`);
  return category;
}

async function hubPage(site: Site, product: ProductView): Promise<string> {
  const category = categoryOf(site, product);
  if (!category.component_hub)
    throw new Error(`prerender: ${product.id} has a hub but its category names no hub path`);
  const at = hubPath(category.component_hub, product.slug);
  const { products, total } = await site.repo.listing({ uses: product.id, sort: "name" }, 1, PAGE_SIZE);
  writePage(site, `${at.slice(1)}.html`, buildHubHeadMeta(componentHub(product, category, products, total), site.base),
    await site.render({ name: "hub", path: category.component_hub, slug: product.id, page: 1 }));
  return at;
}

async function productPages(site: Site, product: ProductView): Promise<ProductPages> {
  const history = product.history ? await site.repo.history(product.id) : null;
  const head = buildProductHeadMeta(productSeo(product, site.registry, DEFAULT_VALUE_LABELS), site.base);
  writePage(site, `product/${product.slug}.html`, head,
    await site.render({ name: "product-detail", productId: product.id }), product);
  if (history) writePage(site, `product/${product.slug}/history.html`,
    { ...head, canonicalUrl: `${site.base}${historyPath(product.slug)}` },
    await site.render({ name: "product-history", productId: product.id }));
  const compared = product.models.length > 1;
  if (compared) writePage(site, `compare/${product.slug}.html`,
    buildHubHeadMeta(familyCompare(product, categoryOf(site, product)), site.base),
    await site.render({ name: "compare", query: "", family: product.slug }));
  return { id: product.id, slug: product.slug, indexable: product.indexable, history: history !== null,
    modified: lastmod(product, history), hub: product.hub ? await hubPage(site, product) : undefined, compared,
    components: product.components.map((c) => c.id) };
}

const port = parentPort;
if (!port) throw new Error("prerender: worker.ts runs as a worker thread of main.ts");
// Justification (typed boundary): main.ts starts this worker with the page template as its data.
const site = openSite(workerData as string);
port.on("message", async (ids: readonly string[]) => {
  const opened = await site;
  port.postMessage(await Promise.all((await opened.repo.products(ids)).map((p) => productPages(opened, p))));
});
