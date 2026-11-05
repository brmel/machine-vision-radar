import { type FC, useMemo, useState } from "react";
import type { CatalogRepository } from "../../../domain/ports/CatalogRepository.ts";
import type { ProductView } from "../../../domain/views.ts";
import { useRegistry, Breadcrumbs } from "../../../ui/index.ts";
import { browsePath } from "../../../domain/paths.ts";
import { buildProductHeadMeta, productSeo } from "../../../shell/seo/product.ts";
import { useRecordHead } from "../../../shell/seo/documentHead.ts";
import { SITE_ORIGIN } from "../../../shell/seo/siteOrigin.ts";
import { ProductTabs, type ProductDetailTab } from "./ProductTabs.tsx";
import { ProductHeader, type ProductHeaderProps } from "../header/ProductHeader.tsx";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useValueLabels } from "../../../shell/i18n/labels.ts";
import { DetailState } from "../../../shell/layout/DetailState.tsx";
import type { ReportInbox } from "../../../domain/ports/review/ReportInbox.ts";
import { ReportError } from "./ReportError.tsx";
import { useProduct } from "../useProduct.ts";

interface ProductDetailViewProps extends Omit<ProductHeaderProps, "product" | "category"> {
  repository: CatalogRepository;
  productId: string;
  prerendered: ProductView | null;
  reports: ReportInbox;
}

export const ProductDetailView: FC<ProductDetailViewProps> = ({ repository, productId, prerendered, reports,
  ...header }) => {
  const { t } = useI18n();
  const registry = useRegistry();
  const [activeTab, setActiveTab] = useState<ProductDetailTab>("specs");
  const { value: product, isLoading, error } = useProduct(repository, productId, prerendered);
  const category = product ? registry.categories.find((c) => c.id === product.category) ?? null : null;

  const valueLabels = useValueLabels();
  const headMeta = useMemo(() => {
    if (!product || !category) return null;
    return buildProductHeadMeta(productSeo(product, registry, valueLabels), SITE_ORIGIN);
  }, [product, category, registry, valueLabels]);

  useRecordHead(headMeta, !isLoading && !error, t("productNotFound"));

  if (isLoading || error || !product || !category) {
    const trail = <Breadcrumbs label={t("breadcrumbLabel")}
      trail={[{ label: t("catalogTitle"), href: browsePath(""), onOpen: header.onBrowse }]} />;
    return <DetailState loading={isLoading} failed={error} trail={trail} missing={t("productNotFound")}
      skeleton={{ count: 6, type: "row" }} />;
  }

  return (
    <div className="space-y-3">
      <ProductHeader product={product} category={category} {...header} />
      <ProductTabs product={product} activeTab={activeTab} onTabChange={setActiveTab}
        onSelectProduct={header.onSelectProduct} />
      <ReportError inbox={reports} subject={product.id} />
    </div>
  );
};
