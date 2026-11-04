import { type FC, type ReactNode, useEffect, useMemo } from "react";
import type { CatalogRepository } from "../../../domain/ports/CatalogRepository.ts";
import { PAGE_SIZE } from "../../../domain/ports/CatalogRepository.ts";
import { categoryPath, productPath, vendorPath } from "../../../domain/paths.ts";
import { AppLink, Breadcrumbs, PageHeader, Pagination, ProductCard, ReadState, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { usePagerLabels, useReadStateLabels, useValueLabels } from "../../../shell/i18n/labels.ts";
import { buildHubHeadMeta, componentHub } from "../../../shell/seo/hubs.ts";
import { syncDocumentHead } from "../../../shell/seo/documentHead.ts";
import { SITE_ORIGIN } from "../../../shell/seo/siteOrigin.ts";
import { useComponentHub } from "../hooks/useComponentHub.ts";

interface ComponentHubProps {
  repository: CatalogRepository;
  path: string;
  slug: string;
  page: number;
  onPage: (page: number) => void;
  onSelectProduct: (slug: string) => void;
  onSelectVendor: (slug: string) => void;
  onSelectCategory: (category: string) => void;
  onMissing: () => void;
  news: (about: string) => ReactNode;
}

export const ComponentHub: FC<ComponentHubProps> = ({ repository, path, slug, page, onPage, onSelectProduct,
  onSelectVendor, onSelectCategory, onMissing, news }) => {
  const { t, plural, locale } = useI18n();
  const valueLabels = useValueLabels();
  const pager = usePagerLabels();
  const states = useReadStateLabels();
  const hub = useComponentHub(repository, path, slug, page);
  const head = useMemo(() => (hub.phase === "ready"
    ? buildHubHeadMeta(componentHub(hub.product, hub.category, hub.users, hub.total), SITE_ORIGIN) : null), [hub]);
  useEffect(() => {
    if (head) syncDocumentHead(head);
  }, [head]);
  useEffect(() => {
    if (hub.phase === "missing") onMissing();
  }, [hub.phase, onMissing]);

  if (hub.phase !== "ready") {
    return <ReadState failed={hub.phase === "error"} labels={states} skeleton={{ count: 6 }} />;
  }

  const { product, category, total, users } = hub;
  return (
    <div className="space-y-3">
      <Breadcrumbs label={t("breadcrumbLabel")} trail={[{ label: localized(category.label, locale),
        href: categoryPath(category.id), onOpen: () => onSelectCategory(category.id) }]} />
      <PageHeader title={product.name} lead={
        <>
          <p role="status">{plural("hubLeadOne", "hubLeadOther", total).replace("{name}", product.name)}</p>
          <AppLink href={productPath(product.slug)} onOpen={() => onSelectProduct(product.slug)}
            className="text-caption underline">{t("hubProductLink", { name: product.name })}</AppLink>
        </>
      } />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
        {users.map((u) => (
          <ProductCard key={u.id} product={u} valueLabels={valueLabels}
            link={{ href: productPath(u.slug), onOpen: () => onSelectProduct(u.slug) }}
            vendorLink={{ href: vendorPath(u.vendor), onOpen: () => onSelectVendor(u.vendor) }} />
        ))}
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} totalCount={total}
        onPageChange={onPage} {...pager} />
      {news(product.id)}
    </div>
  );
};
