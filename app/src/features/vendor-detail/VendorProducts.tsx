import type { FC } from "react";
import { PAGE_SIZE } from "../../domain/ports/CatalogRepository.ts";
import type { ProductCard as Card } from "../../domain/views.ts";
import { productPath } from "../../domain/paths.ts";
import { Pagination, ProductCard, StatePanel, Section } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { useCompareControl, usePagerLabels, useValueLabels } from "../../shell/i18n/labels.ts";

interface VendorProductsProps {
  products: readonly Card[];
  total: number;
  page: number;
  onPage: (page: number) => void;
  onSelectProduct: (productSlug: string) => void;
  onToggleCompare: (productId: string) => void;
  comparedIds: string[];
}

export const VendorProducts: FC<VendorProductsProps> = ({ products, total, page, onPage, onSelectProduct,
  onToggleCompare, comparedIds }) => {
  const { t } = useI18n();
  const goToPage = (next: number) => {
    onPage(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const compareOf = useCompareControl(comparedIds, onToggleCompare);
  const valueLabels = useValueLabels();
  const pager = usePagerLabels();
  return (
    <Section title={t("vendorProductsTitle")}>
      {products.length === 0 ? (
        <StatePanel tone="empty" title={t("noVendorProducts")} />
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} valueLabels={valueLabels}
              link={{ href: productPath(p.slug), onOpen: () => onSelectProduct(p.slug) }} compare={compareOf(p.id)} />
          ))}
        </div>
      )}
      {total > PAGE_SIZE && (
        <div className="pt-3 border-t border-line">
          <Pagination page={page} pageSize={PAGE_SIZE} totalCount={total}
            onPageChange={goToPage} {...pager} />
        </div>
      )}
    </Section>
  );
};
