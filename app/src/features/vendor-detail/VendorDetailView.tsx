import { type FC, type ReactNode, useMemo } from "react";
import { PAGE_SIZE, type CatalogRepository } from "../../domain/ports/CatalogRepository.ts";
import { Breadcrumbs, DetailState, localized, useRead } from "../../ui/index.ts";
import { browsePath } from "../../domain/paths.ts";
import { buildVendorHeadMeta } from "../../shell/seo/seo.ts";
import { useRecordHead } from "../../shell/seo/documentHead.ts";
import { SITE_ORIGIN } from "../../shell/seo/siteOrigin.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { useDetailStateLabels } from "../../shell/i18n/labels.ts";
import { logger } from "../../shell/logger.ts";
import { OwnershipList } from "./OwnershipList.tsx";
import { VendorHeader } from "./VendorHeader.tsx";
import { VendorProducts } from "./VendorProducts.tsx";

interface VendorDetailViewProps {
  repository: CatalogRepository;
  vendorSlug: string;
  page: number;
  onPage: (page: number) => void;
  onBrowse: () => void;
  onSelectProduct: (productId: string) => void;
  onSelectVendor: (vendorSlug: string) => void;
  onToggleCompare: (productId: string) => void;
  comparedIds: string[];
  news: (about: string) => ReactNode;
}

export const VendorDetailView: FC<VendorDetailViewProps> = ({ repository, vendorSlug, page, onPage, onBrowse,
  onSelectProduct, onSelectVendor, onToggleCompare, comparedIds, news }) => {
  const { t, locale } = useI18n();
  const { value, isLoading, error } = useRead(
    () => Promise.all([repository.organization(vendorSlug),
      repository.listing({ vendor: vendorSlug, sort: "name" }, page, PAGE_SIZE)]),
    `vendor:${vendorSlug}?page=${page}`,
    (err) => logger.error("vendor page: the read model failed to load", { vendor: vendorSlug, page }, err),
  );
  const [vendor, listing] = value ?? [null, null];
  const headMeta = useMemo(() => (vendor ? buildVendorHeadMeta({ ...vendor,
    summary: vendor.summary ? localized(vendor.summary, locale) : "" }, SITE_ORIGIN) : null), [vendor, locale]);
  const stateLabels = useDetailStateLabels(t("vendorNotFound"));
  useRecordHead(headMeta, !isLoading && !error, t("vendorNotFound"));

  const trail = <Breadcrumbs label={t("breadcrumbLabel")}
    trail={[{ label: t("catalogTitle"), href: browsePath(""), onOpen: onBrowse }]} />;
  if (isLoading || error || !vendor || !listing) {
    return <DetailState loading={isLoading} failed={error} trail={trail} labels={stateLabels}
      skeleton={{ count: 3 }} />;
  }

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        {trail}
        <VendorHeader vendor={vendor} total={listing.total} />
      </div>
      {vendor.ownership.length > 0 && <OwnershipList vendor={vendor} onSelectVendor={onSelectVendor} />}
      <VendorProducts products={listing.products} total={listing.total} page={page} onPage={onPage}
        onSelectProduct={onSelectProduct} onToggleCompare={onToggleCompare} comparedIds={comparedIds} />
      {news(vendor.id)}
    </div>
  );
};
