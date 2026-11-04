import { type FC } from "react";
import type { ProductView } from "../../../domain/views.ts";
import { Button, WebsiteLink } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useCompareControl } from "../../../shell/i18n/labels.ts";

export interface ProductActionsProps {
  product: ProductView;
  onToggleCompare: (productId: string) => void;
  comparedIds: readonly string[];
}

export const ProductActions: FC<ProductActionsProps> = ({ product, onToggleCompare, comparedIds }) => {
  const { t } = useI18n();
  const compare = useCompareControl(comparedIds, onToggleCompare)(product.id);
  return (
    <>
      {product.website_url?.trim() && <WebsiteLink href={product.website_url} label={t("officialWebsite")} />}
      <Button variant={compare.pressed ? "secondary" : "outline"} size="sm" disabled={compare.disabled}
        onClick={compare.onToggle}>{compare.label}</Button>
    </>
  );
};
