import type { FC } from "react";
import type { CatalogRepository } from "../../domain/ports/CatalogRepository.ts";
import type { ProductView } from "../../domain/views.ts";
import { PageHeader, StatePanel, Table, localized, termLabel, useRead, useRegistry } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { logger } from "../../shell/logger.ts";
import { CompareActions } from "./CompareActions.tsx";
import { ReadState } from "../../shell/layout/ReadState.tsx";
import { CompareHead } from "./table/CompareHead.tsx";
import { CompareSection } from "./table/CompareSection.tsx";
import { CompareTableRow, STICKY } from "./table/CompareTableRow.tsx";
import { allEqual, compareGroups, compareQuery, showsOnlyDifferences } from "../../domain/compare.ts";

interface CompareViewProps {
  repository: CatalogRepository;
  comparedIds: string[];
  onComparedIdsChange: (ids: string[]) => void;
  query: string;
  onQueryChange: (query: string) => void;
  onSelectProduct: (productSlug: string) => void;
  onBrowseMore: () => void;
}

export const CompareView: FC<CompareViewProps> = ({ repository, comparedIds, onComparedIdsChange, query, onQueryChange,
  onSelectProduct, onBrowseMore }) => {
  const { t, locale } = useI18n();
  const { spec_definitions: specDefs, categories, domains } = useRegistry();
  const ids = comparedIds.join(",");
  const read = useRead(() => Promise.all(comparedIds.map((id) => repository.product(id))), `compare:${ids}`,
    (err) => logger.error("compare: products failed to load", { ids }, err));
  const products = ids ? (read.value ?? []).filter((p): p is ProductView => p !== null) : [];
  const isLoading = ids !== "" && read.isLoading;
  const error = ids !== "" && read.error;
  const remove = (id: string) => () => onComparedIdsChange(comparedIds.filter((x) => x !== id));
  const clearAll = () => onComparedIdsChange([]);
  const onlyDifferences = showsOnlyDifferences(query);

  if (isLoading || error || products.length === 0) {
    return (
      <div className="space-y-3">
        <PageHeader title={t("compareTitle")} lead={t("compareSubtitle")} />
        {isLoading || error ? (
          <ReadState failed={error} skeleton={{ count: 3, type: "row" }} level={2} />
        ) : (
          <StatePanel tone="empty" title={t("compareEmptyTitle")}
            action={{ label: t("addProductsToCompare"), onClick: onBrowseMore }} />
        )}
      </div>
    );
  }

  const categoryById = (p: ProductView) => {
    const category = categories.find((c) => c.id === p.category);
    if (!category) throw new Error(`compare: category ${p.category} is not in the read model`);
    return category;
  };
  const categoryOf = (p: ProductView) => localized(categoryById(p).label, locale);
  const domainOf = (p: ProductView) => termLabel(domains, categoryById(p).domain, locale);
  const shows = (equal: boolean) => !(onlyDifferences && equal);
  const toggleDifferences = () => onQueryChange(compareQuery(comparedIds, !onlyDifferences));
  const kinds = [
    { key: "domain", label: t("specRowDomain"), cell: domainOf },
    { key: "category", label: t("specRowCategory"), cell: categoryOf },
  ].filter((r) => shows(allEqual(products, r.cell)));
  const head = (p: ProductView) =>
    <CompareHead product={p} glyph={categoryById(p).glyph} onOpen={onSelectProduct} onRemove={remove(p.id)} />;

  return (
    <div className="space-y-3">
      <PageHeader title={t("compareTitle")} lead={t("compareSubtitle")} actions={
        <CompareActions onlyDifferences={onlyDifferences} onToggleDifferences={toggleDifferences} onClear={clearAll}
          onBrowseMore={onBrowseMore} />
      } />
      <Table className="text-caption" columns={[
        { head: t("specParamHeading"), className: `${STICKY} bg-sunken` },
        ...products.map((p) => ({ head: head(p), className: "max-sm:px-1.5 sm:min-w-44 max-w-72 align-top" })),
      ]}>
        {kinds.map((r) => <CompareTableRow key={r.key} label={r.label} products={products} cell={r.cell} />)}
        {compareGroups(products, specDefs).map(({ section, rows }) => {
          const keys = rows.filter((r) => shows(r.equal)).map((r) => r.key);
          return keys.length === 0 ? null
            : <CompareSection key={section} section={section} keys={keys} products={products} />;
        })}
      </Table>
    </div>
  );
};
