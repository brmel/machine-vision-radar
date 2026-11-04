import type { FC } from "react";
import { PAGE_SIZE } from "../../../domain/ports/CatalogRepository.ts";
import type { CategoryEntry } from "../../../domain/views.ts";
import type { BrowseView } from "../../../domain/filtering/browseView.ts";
import type { BrowseFilters } from "../../../domain/filtering/filterUrl.ts";
import { productPath, vendorPath } from "../../../domain/paths.ts";
import { withColumn, withPage, withoutFilters } from "../../../domain/filtering/filterTransitions.ts";
import { Pagination, ProductCard, StatePanel } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useCompareControl, usePagerLabels, useValueLabels } from "../../../shell/i18n/labels.ts";
import { ResultsTable } from "../components/ResultsTable.tsx";

interface BrowseResultsProps {
  hub: CategoryEntry | undefined;
  view: BrowseView;
  change: (next: BrowseFilters) => void;
  onOpen: (productSlug: string) => void;
  onSelectVendor: (vendorSlug: string) => void;
  onToggleCompare: (productId: string) => void;
  comparedIds: string[];
}

export const BrowseResults: FC<BrowseResultsProps> = ({ hub, view, change, onOpen, onSelectVendor, onToggleCompare,
  comparedIds }) => {
  const { t } = useI18n();
  const f = view.filters;
  const valueLabels = useValueLabels();
  const pager = usePagerLabels();
  const compareOf = useCompareControl(comparedIds, onToggleCompare);
  const goToPage = (page: number) => {
    change(withPage(f, page));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const table = hub && f.layout === "table" ? hub : undefined;

  return (
    <div className="flex-1 w-full min-w-0 space-y-3">
      {view.products.length === 0 ? (
        <StatePanel tone="empty" title={t("noMatchingProducts")}
          action={{ label: t("resetFiltersAction"), onClick: () => change(withoutFilters(f)) }} />
      ) : table ? (
        <ResultsTable
          products={view.products}
          hub={table}
          column={f.column}
          onSort={(key) => change(withColumn(f, key))}
          onSelectProduct={onOpen}
        />
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
          {view.products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              valueLabels={valueLabels}
              link={{ href: productPath(product.slug), onOpen: () => onOpen(product.slug) }}
              vendorLink={{ href: vendorPath(product.vendor), onOpen: () => onSelectVendor(product.vendor) }}
              showCategory={!hub}
              compare={compareOf(product.id)}
            />
          ))}
        </div>
      )}
      {view.totalPages > 1 && (
        <div className="pt-3 border-t border-line">
          <Pagination
            page={view.page}
            pageSize={PAGE_SIZE}
            totalCount={view.resultCount}
            onPageChange={goToPage}
            {...pager}
          />
        </div>
      )}
    </div>
  );
};
