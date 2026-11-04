import type { CategoryPage, FeedItemView, FeedPageView, HistoryView, MarketView, OrgBrief, OrganizationView,
  ProductCard, ProductView, RegistryView } from "../views.ts";

export interface ListingQuery {
  readonly categories?: readonly string[];
  readonly vendor?: string;
  readonly uses?: string;
  readonly sort: "name" | "name-desc" | "vendor";
}

export const PAGE_SIZE = 20;

export interface ListingPage {
  readonly products: readonly ProductCard[];
  readonly total: number;
}

export interface CatalogRepository {
  registry(): Promise<RegistryView>;
  product(slugOrId: string): Promise<ProductView | null>;
  products(ids: readonly string[]): Promise<readonly ProductView[]>;
  listing(query: ListingQuery, page: number, size: number): Promise<ListingPage>;
  categoryPage(category: string, cursor?: string): Promise<CategoryPage>;
  organizations(): Promise<readonly OrgBrief[]>;
  organization(slug: string): Promise<OrganizationView | null>;
  organizationViews(slugs: readonly string[]): Promise<readonly OrganizationView[]>;
  history(productId: string): Promise<HistoryView | null>;
  news(): Promise<FeedPageView>;
  article(slug: string): Promise<FeedItemView | null>;
  market(): Promise<MarketView>;
}
