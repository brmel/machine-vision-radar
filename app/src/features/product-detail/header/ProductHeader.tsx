import { type FC } from "react";
import type { CategoryEntry } from "../../../domain/views.ts";
import { browseQuery } from "../../../domain/filtering/filterUrl.ts";
import { browsePath, categoryPath, vendorPath } from "../../../domain/paths.ts";
import { AppLink, Badge, Breadcrumbs, Facts, PageHeader, StatusBadge, SourceChip, Thumb, localized, formatCountry,
  termLabel, useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { ProductActions, type ProductActionsProps } from "./ProductActions.tsx";
import { ProductLinks, type ProductLinksProps } from "./ProductLinks.tsx";

export interface ProductHeaderProps extends ProductLinksProps, ProductActionsProps {
  category: CategoryEntry;
  onBrowse: () => void;
  onSelectDomain: (domain: string) => void;
  onSelectCategory: (categoryId: string) => void;
  onSelectVendor: (vendorSlug: string) => void;
}

export const ProductHeader: FC<ProductHeaderProps> = ({ product, category, onBrowse, onSelectDomain, onSelectCategory,
  onSelectVendor, onSelectProduct, onOpenHistory, onOpenHub, ...compare }) => {
  const { t, locale } = useI18n();
  const { pipeline_stages: stages, domains } = useRegistry();
  const vendor = product.vendor;
  const statusSource = product.status?.source ? product.sources.find((src) => src.id === product.status?.source)
    : undefined;
  return (
    <div className="space-y-1">
      <Breadcrumbs label={t("breadcrumbLabel")} trail={[
        { label: t("catalogTitle"), href: browsePath(""), onOpen: onBrowse },
        { label: termLabel(domains, category.domain, locale),
          href: browsePath(browseQuery({ domain: category.domain })), onOpen: () => onSelectDomain(category.domain) },
        { label: localized(category.label, locale), href: categoryPath(category.id),
          onOpen: () => onSelectCategory(category.id) },
      ]} />
      <PageHeader
        title={product.name}
        media={<Thumb url={product.thumbnail_url} glyph={category.glyph} size="md" />}
        actions={<ProductActions product={product} {...compare} />}
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
          <span className="inline-flex flex-wrap items-center gap-x-1.5">
            <AppLink href={vendorPath(vendor.slug)} onOpen={() => onSelectVendor(vendor.slug)}
              className="text-body font-medium text-fg-secondary underline hover:text-fg">{vendor.name}</AppLink>
            {vendor.country && <span>· {formatCountry(vendor.country, locale)}</span>}
          </span>
          {product.status && (
            <span className="status-line inline-flex flex-wrap items-center gap-1.5">
              <StatusBadge status={product.status.term} locale={locale} />
              {statusSource && <SourceChip source={statusSource} locale={locale} />}
            </span>
          )}
          <span data-stages className="inline-flex flex-wrap items-center gap-1.5">
            <span>{t("filterByPipeline")}</span>
            {category.pipeline.map((id) => <Badge key={id}>{termLabel(stages, id, locale)}</Badge>)}
          </span>
          <ProductLinks product={product} onSelectProduct={onSelectProduct} onOpenHistory={onOpenHistory}
            onOpenHub={onOpenHub} />
        </div>
        {product.identifiers.length > 0 && (
          <Facts layout="inline" className="text-caption" facts={product.identifiers.map((i) => ({
            key: `${i.scheme.id}:${i.value}`, label: localized(i.scheme.label, locale),
            value: <span className="font-mono wrap-anywhere">{i.value}</span>,
          }))} />
        )}
      </PageHeader>
    </div>
  );
};
