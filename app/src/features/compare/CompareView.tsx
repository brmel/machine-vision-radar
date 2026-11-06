import { useMemo, type FC } from "react";
import type { CatalogRepository } from "../../domain/ports/CatalogRepository.ts";
import type { ProductView } from "../../domain/views.ts";
import { PageHeader, Table, localized, termLabel, useRead, useRegistry } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { logger } from "../../shell/logger.ts";
import { buildHubHeadMeta, familyCompare } from "../../shell/seo/hubs.ts";
import { useRecordHead } from "../../shell/seo/documentHead.ts";
import { SITE_ORIGIN } from "../../shell/seo/siteOrigin.ts";
import { CompareActions } from "./CompareActions.tsx";
import { CompareEmpty } from "./CompareEmpty.tsx";
import { CompareHead } from "./table/CompareHead.tsx";
import { CompareSection } from "./table/CompareSection.tsx";
import { CompareTableRow, STICKY } from "./table/CompareTableRow.tsx";
import { allEqual, compareGroups, compareQuery, showsOnlyDifferences } from "../../domain/compare.ts";

interface CompareViewProps {
  repository: CatalogRepository;
  comparedIds: string[];
  onComparedIdsChange: (ids: string[]) => void;
  query: string;
  family?: string;
  onQueryChange: (query: string, family?: string) => void;
  onSelectProduct: (productSlug: string) => void;
  onBrowseMore: () => void;
}

interface Compared {
  readonly family: ProductView | null;
  readonly products: readonly ProductView[];
}

async function picked(repository: CatalogRepository, ids: readonly string[]): Promise<Compared> {
  const read = await Promise.all(ids.map((id) => repository.product(id)));
  return { family: null, products: read.filter((p): p is ProductView => p !== null) };
}

async function familyModels(repository: CatalogRepository, slug: string): Promise<Compared> {
  const family = await repository.product(slug);
  return { family, products: family ? await repository.products(family.models.map((m) => m.id)) : [] };
}

function headed(family: ProductView | null | undefined, t: ReturnType<typeof useI18n>["t"]): [string, string] {
  if (!family) return [t("compareTitle"), t("compareSubtitle")];
  const named = { name: family.name, vendor: family.vendor.name, count: family.models.length };
  return [t("compareFamilyTitle", named), t("compareFamilyLead", named)];
}

export const CompareView: FC<CompareViewProps> = ({ repository, comparedIds, onComparedIdsChange, query, family,
  onQueryChange, onSelectProduct, onBrowseMore }) => {
  const { t, locale } = useI18n();
  const { spec_definitions: specDefs, categories, domains } = useRegistry();
  const ids = comparedIds.join(",");
  const asked = family ? `family:${family}` : ids;
  const read = useRead(() => (family ? familyModels(repository, family) : picked(repository, comparedIds)),
    `compare:${asked}`, (err) => logger.error("compare: products failed to load", { asked }, err));
  const products = read.value?.products ?? [];
  const isLoading = asked !== "" && read.isLoading;
  const error = asked !== "" && read.error;
  const categoryById = (p: ProductView) => {
    const category = categories.find((c) => c.id === p.category);
    if (!category) throw new Error(`compare: category ${p.category} is not in the read model`);
    return category;
  };
  const head = useMemo(() => (read.value?.family
    ? buildHubHeadMeta(familyCompare(read.value.family, categoryById(read.value.family)), SITE_ORIGIN) : null),
  [read.value]);
  useRecordHead(head, family !== undefined && !isLoading && !error, t("productNotFound"));
  const onlyDifferences = showsOnlyDifferences(query);
  const [title, lead] = headed(read.value?.family, t);
  const remove = (id: string) => () => onComparedIdsChange(comparedIds.filter((x) => x !== id));
  const clearAll = () => {
    onComparedIdsChange([]);
    if (family) onQueryChange("");
  };

  if (isLoading || error || products.length === 0) {
    return (
      <div className="space-y-3">
        <PageHeader title={title} lead={lead} />
        <CompareEmpty loading={isLoading} failed={error} missing={family !== undefined} onBrowseMore={onBrowseMore} />
      </div>
    );
  }

  const categoryOf = (p: ProductView) => localized(categoryById(p).label, locale);
  const domainOf = (p: ProductView) => termLabel(domains, categoryById(p).domain, locale);
  const shows = (equal: boolean) => !(onlyDifferences && equal);
  const toggleDifferences = () => onQueryChange(compareQuery(family ? [] : comparedIds, !onlyDifferences), family);
  const kinds = [
    { key: "domain", label: t("specRowDomain"), cell: domainOf },
    { key: "category", label: t("specRowCategory"), cell: categoryOf },
  ].filter((r) => shows(allEqual(products, r.cell)));
  const column = (p: ProductView) =>
    <CompareHead product={p} glyph={categoryById(p).glyph} onOpen={onSelectProduct}
      onRemove={family ? undefined : remove(p.id)} />;

  return (
    <div className="space-y-3">
      <PageHeader title={title} lead={lead} actions={
        <CompareActions onlyDifferences={onlyDifferences} onToggleDifferences={toggleDifferences} onClear={clearAll}
          onBrowseMore={onBrowseMore} />
      } />
      <Table className="text-caption" columns={[
        { head: t("specParamHeading"), className: `${STICKY} bg-sunken` },
        ...products.map((p) => ({ head: column(p), className: "max-sm:px-1.5 sm:min-w-44 max-w-72 align-top" })),
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
