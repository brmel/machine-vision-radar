import { z } from "zod";
import { listingOrder } from "../../domain/filtering/browseView.ts";
import { isProductId } from "../../domain/paths.ts";
import type { CatalogRepository, ListingPage, ListingQuery } from "../../domain/ports/CatalogRepository.ts";
import type { CategoryPage, FeedItemView, FeedPageView, HistoryView, IndexView, MarketView, OrgBrief, OrganizationView,
  ProductView, RegistryView } from "../../domain/views.ts";
import {
  CategoryPageSchema, FeedItemViewSchema, FeedPageViewSchema, HistoryViewSchema, IndexViewSchema, MarketViewSchema,
  OrgBriefSchema, OrganizationViewSchema, ProductViewSchema, RegistryViewSchema,
} from "../generated-views-zod.ts";
import { Recent } from "./recent.ts";

const OrganizationsSchema = z.array(OrgBriefSchema);

type Loader = (file: string) => Promise<unknown>;

const httpLoader: Loader = async (file) => {
  const res = await fetch(`/read-model/${file}`, { headers: { Accept: "application/json" } });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`read model: ${file} answered HTTP ${res.status}`);
  return res.json();
};

export class FilesCatalogRepository implements CatalogRepository {
  private readonly recent = new Recent<unknown>();
  private readonly loader: Loader;

  constructor(loader: Loader = httpLoader) {
    this.loader = loader;
  }

  private load<T>(file: string, schema: z.ZodType<T>): Promise<T | null> {
    const reading =
      this.recent.get(file, () => this.loader(file).then((raw) => (raw === null ? null : schema.parse(raw))));
    // Justification (typed boundary): each file is kept under one name and always parsed by the same schema.
    return reading as Promise<T | null>;
  }

  private async required<T>(file: string, schema: z.ZodType<T>): Promise<T> {
    const found = await this.load(file, schema);
    if (found === null) throw new Error(`read model: no ${file}`);
    return found;
  }

  registry(): Promise<RegistryView> {
    return this.required("registry.json", RegistryViewSchema);
  }

  private index(): Promise<IndexView> {
    return this.required("index.json", IndexViewSchema);
  }

  async product(slugOrId: string): Promise<ProductView | null> {
    const id = isProductId(slugOrId) ? slugOrId : (await this.index()).products.find((p) => p.slug === slugOrId)?.id;
    return id ? this.load(`products/${id}.json`, ProductViewSchema) : null;
  }

  products(ids: readonly string[]): Promise<readonly ProductView[]> {
    return Promise.all(ids.map((id) => this.required(`products/${id}.json`, ProductViewSchema)));
  }

  async listing(query: ListingQuery, page: number, size: number): Promise<ListingPage> {
    const listed = (await this.index()).products.filter((c) =>
      (!query.categories || query.categories.includes(c.category)) && (!query.vendor || c.vendor === query.vendor));
    const users = query.uses ? new Set((await this.products(listed.map((c) => c.id)))
      .filter((v) => v.components.some((c) => c.id === query.uses)).map((v) => v.id)) : null;
    const cards = users ? listed.filter((c) => users.has(c.id)) : listed;
    const ordered = [...cards].sort(listingOrder(query.sort));
    return { products: ordered.slice((page - 1) * size, page * size), total: ordered.length };
  }

  categoryPage(category: string, cursor = "1"): Promise<CategoryPage> {
    return this.required(`categories/${encodeURIComponent(category)}/${encodeURIComponent(cursor)}.json`,
      CategoryPageSchema);
  }

  organizations(): Promise<readonly OrgBrief[]> {
    return this.required("organizations.json", OrganizationsSchema);
  }

  organization(slug: string): Promise<OrganizationView | null> {
    return this.load(`organizations/${encodeURIComponent(slug)}.json`, OrganizationViewSchema);
  }

  organizationViews(slugs: readonly string[]): Promise<readonly OrganizationView[]> {
    return Promise.all(slugs.map((slug) =>
      this.required(`organizations/${encodeURIComponent(slug)}.json`, OrganizationViewSchema)));
  }

  history(productId: string): Promise<HistoryView | null> {
    return this.load(`history/${encodeURIComponent(productId)}.json`, HistoryViewSchema);
  }

  news(): Promise<FeedPageView> {
    return this.required("news.json", FeedPageViewSchema);
  }

  article(slug: string): Promise<FeedItemView | null> {
    return this.load(`news/${encodeURIComponent(slug)}.json`, FeedItemViewSchema);
  }

  market(): Promise<MarketView> {
    return this.required("market.json", MarketViewSchema);
  }
}
