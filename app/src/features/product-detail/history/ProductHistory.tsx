import { type FC } from "react";
import type { CatalogRepository } from "../../../domain/ports/CatalogRepository.ts";
import { Breadcrumbs, DetailState, PageHeader, StatePanel, useRead } from "../../../ui/index.ts";
import { browsePath, productPath } from "../../../domain/paths.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useDetailStateLabels } from "../../../shell/i18n/labels.ts";
import { logger } from "../../../shell/logger.ts";
import { HistoryVersion } from "./HistoryVersion.tsx";

interface ProductHistoryProps {
  repository: CatalogRepository;
  productId: string;
  onBrowse: () => void;
  onSelectProduct: (slug: string) => void;
}

export const ProductHistory: FC<ProductHistoryProps> = ({ repository, productId, onBrowse, onSelectProduct }) => {
  const { t } = useI18n();
  const read = useRead(
    () => repository.product(productId)
      .then(async (product) => ({ product, history: product ? await repository.history(product.id) : null })),
    `history:${productId}`,
    (err) => logger.error("history page: failed to load", { product: productId }, err),
  );
  const labels = useDetailStateLabels(t("productNotFound"));
  const catalog = { label: t("catalogTitle"), href: browsePath(""), onOpen: onBrowse };
  if (read.error || !read.value?.product) {
    return <DetailState loading={read.isLoading} failed={read.error} trail={<Breadcrumbs label={t("breadcrumbLabel")}
      trail={[catalog]} />} labels={labels} skeleton={{ count: 3, type: "row" }} />;
  }
  const { product, history } = read.value;
  const versions = history?.versions ?? [];

  return (
    <div className="space-y-3">
      <Breadcrumbs label={t("breadcrumbLabel")} trail={[catalog,
        { label: product.name, href: productPath(product.slug), onOpen: () => onSelectProduct(product.slug) }]} />
      <PageHeader title={t("historyTitle", { name: product.name })} lead={t("historyIntro")} />
      {versions.length === 0 ? (
        <StatePanel tone="empty" title={t("historyEmpty")} />
      ) : (
        <ol className="history divide-y divide-line rounded-card border border-line bg-surface">
          {versions.map((v) => <HistoryVersion key={`${v.entity}-${v.version}`} version={v} productId={product.id} />)}
        </ol>
      )}
    </div>
  );
};
