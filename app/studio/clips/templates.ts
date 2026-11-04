import type { CatalogRepository } from "../../src/domain/ports/CatalogRepository.ts";
import type { ProductView, RegistryView } from "../../src/domain/views.ts";
import { DEFAULT_LANGUAGE } from "../../src/domain/languages.ts";
import { articlePath, vendorPath } from "../../src/domain/paths.ts";
import { DEFAULT_MESSAGES as messages, DEFAULT_VALUE_LABELS, fill, plural } from "../../src/shell/i18n/messages.ts";
import { formatSpecLabel, formatSpecValueText, localized } from "../../src/ui/specs/specFormat.ts";
import { asking, comparing, heldFor, reading, sourcing, type Step } from "../footage/flows.ts";
import type { ClipScript } from "./script.ts";

export type Card = { readonly kind: "catalog" } | { readonly kind: "product"; readonly product: ProductView };

export interface Post {
  readonly name: string;
  readonly steps: readonly Step[];
  readonly card: Card | null;
  readonly script: ClipScript;
}

const CARD_SECONDS = 4;
const LOCALE = DEFAULT_LANGUAGE.code;

async function productOf(repo: CatalogRepository, id: string | undefined): Promise<ProductView> {
  const product = id ? await repo.product(id) : null;
  if (!product) throw new Error(`studio: the read model holds no product ${id ?? ""}`);
  return product;
}

const keySpecs = (product: ProductView, registry: RegistryView): string =>
  product.core.filter((c) => c.value !== undefined).slice(0, 3)
  .map((c) => `${formatSpecLabel(c.key, registry.spec_definitions, LOCALE)} ${formatSpecValueText(c.value,
    DEFAULT_VALUE_LABELS)}`).join(" · ");

const footage = (steps: readonly Step[], caption: string): ClipScript["segments"][number] =>
  ({ shows: "footage", caption, seconds: heldFor(steps) });
const card = { shows: "card", caption: messages.principleProvenance, seconds: CARD_SECONDS } as const;

export type Template = (repo: CatalogRepository, id: string | undefined) => Promise<Post>;

export const TEMPLATES = {
  product: async (repo, id) => {
    const product = await productOf(repo, id);
    const steps = sourcing(product);
    const segments = [footage(steps, keySpecs(product, await repo.registry())), card];
    return { name: `product-${product.slug}`, steps, card: { kind: "product", product },
      script: { hook: product.name, about: [product.slug], segments } };
  },
  compare: async (repo, id) => {
    const product = await productOf(repo, id);
    const peers = (await repo.listing({ categories: [product.category], sort: "name" }, 1, 2)).products;
    const peer = peers.find((p) => p.id !== product.id);
    if (!peer) throw new Error(`studio: no other product of ${product.category} to compare ${product.name} with`);
    const other = await productOf(repo, peer.id);
    const steps = comparing(product, other);
    const script = { hook: `${product.name} · ${other.name}`, about: [product.slug, other.slug],
      segments: [footage(steps, messages.compareTitle)] };
    return { name: `compare-${product.slug}`, steps, card: null, script };
  },
  ask: async (repo, id) => {
    const product = await productOf(repo, id);
    const question = `${product.name}?`;
    const steps = asking(question);
    return { name: `ask-${product.slug}`, steps, card: null,
      script: { hook: question, about: [product.slug], segments: [footage(steps, messages.askNote)] } };
  },
  vendor: async (repo, id) => {
    const vendor = id ? await repo.organization(id) : null;
    if (!vendor) throw new Error(`studio: the read model holds no vendor ${id ?? ""}`);
    const { total } = await repo.listing({ vendor: vendor.slug, sort: "name" }, 1, 1);
    const steps = reading(vendorPath(vendor.slug));
    const count = plural(messages, DEFAULT_LANGUAGE.intl, "productCountOne", "productCountOther", total);
    return { name: `vendor-${vendor.slug}`, steps, card: null,
      script: { hook: vendor.name, about: [vendor.slug], segments: [footage(steps, count)] } };
  },
  article: async (repo, id) => {
    const article = id ? await repo.article(id) : null;
    if (!article) throw new Error(`studio: the read model holds no published article ${id ?? ""}`);
    const steps = reading(articlePath(article.slug));
    const script = { hook: localized(article.title, LOCALE), about: [article.slug],
      segments: [footage(steps, localized(article.summary, LOCALE))] };
    return { name: `article-${article.slug}`, steps, card: null, script };
  },
  catalog: async (repo) => {
    const { counts } = await repo.registry();
    const steps = reading("/");
    const hook = fill(messages.liveStats,
      { products: counts.products, vendors: counts.organizations, categories: counts.categories });
    return { name: "catalog", steps, card: { kind: "catalog" },
      script: { hook, about: [], segments: [footage(steps, messages.footerNote), card] } };
  },
} satisfies Record<string, Template>;

export async function facts(repo: CatalogRepository, about: readonly string[]): Promise<string> {
  const registry = await repo.registry();
  const records = await Promise.all(about.map(async (named) => {
    const product = await repo.product(named);
    if (product) return product;
    const vendor = await repo.organization(named);
    if (vendor) return [vendor, (await repo.listing({ vendor: vendor.slug, sort: "name" }, 1, 1)).total];
    const article = await repo.article(named);
    if (article) return article;
    throw new Error(`studio: the read model holds no product, vendor or article ${named}`);
  }));
  return JSON.stringify([registry.counts, registry.data_as_of, records]);
}
