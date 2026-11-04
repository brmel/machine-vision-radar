import { PAGE_SIZE, type CatalogRepository } from "../../../domain/ports/CatalogRepository.ts";
import type { CategoryEntry, ProductCard, ProductView } from "../../../domain/views.ts";
import { useRead } from "../../../ui/index.ts";
import { logger } from "../../../shell/logger.ts";

type ComponentHubState =
  | { readonly phase: "loading" | "missing" | "error" }
  | { readonly phase: "ready"; readonly product: ProductView; readonly category: CategoryEntry; readonly total: number;
    readonly users: readonly ProductCard[] };

export function useComponentHub(repository: CatalogRepository, path: string, slug: string,
    page: number): ComponentHubState {
  const read = useRead(async (): Promise<ComponentHubState> => {
    const registry = await repository.registry();
    if (!registry.categories.some((c) => c.component_hub === path)) return { phase: "missing" };
    const product = await repository.product(slug);
    const category = registry.categories.find((c) => c.id === product?.category);
    if (!product || !category || category.component_hub !== path || !product.hub) return { phase: "missing" };
    const listing = await repository.listing({ uses: product.id, sort: "name" }, page, PAGE_SIZE);
    return { phase: "ready", product, category, total: listing.total, users: listing.products };
  }, `hub:${path}/${slug}?page=${page}`,
    (err) => logger.error("hub: the read model failed to load", { path, slug, page }, err));
  return read.error ? { phase: "error" } : read.isLoading || !read.value ? { phase: "loading" } : read.value;
}
