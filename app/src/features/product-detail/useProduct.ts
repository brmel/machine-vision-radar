import type { CatalogRepository } from "../../domain/ports/CatalogRepository.ts";
import type { ProductView } from "../../domain/views.ts";
import { useRead, type Read } from "../../ui/index.ts";
import { logger } from "../../shell/logger.ts";

export function useProduct(repository: CatalogRepository, productId: string,
    prerendered: ProductView | null): Read<ProductView | null> {
  const landed = prerendered && [prerendered.id, prerendered.slug].includes(productId) ? prerendered : null;
  const read = useRead(() => repository.product(landed?.id ?? productId), `product:${productId}`,
    (err) => logger.error("product page: failed to load", { product: productId }, err));
  return read.isLoading && landed ? { value: landed, isLoading: false, error: false } : read;
}
