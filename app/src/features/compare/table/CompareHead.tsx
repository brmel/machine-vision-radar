import type { FC } from "react";
import { X } from "lucide-react";
import type { ProductView } from "../../../domain/views.ts";
import { productPath } from "../../../domain/paths.ts";
import { AppLink, StatusBadge, Thumb } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

interface CompareHeadProps {
  product: ProductView;
  glyph: string;
  onOpen: (productSlug: string) => void;
  onRemove?: () => void;
}

export const CompareHead: FC<CompareHeadProps> = ({ product, glyph, onOpen, onRemove }) => {
  const { t, locale } = useI18n();
  const open = () => onOpen(product.slug);
  return (
    <div className="space-y-1 font-normal">
      <div className="flex items-start gap-2">
        <div className="max-sm:hidden"><Thumb url={product.thumbnail_url} glyph={glyph} /></div>
        <div className="min-w-0 flex-1">
          <AppLink href={productPath(product.slug)} onOpen={open}
            className="block wrap-anywhere text-body font-semibold text-fg hover:underline">
            {product.name}
          </AppLink>
          <p className="text-caption text-muted">{product.vendor.name}</p>
        </div>
        {onRemove && (
          <button type="button" onClick={onRemove}
            className="p-1 text-muted hover:text-fg transition-colors cursor-pointer shrink-0"
            aria-label={t("removeFromCompare")}>
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        )}
      </div>
      {product.status && <StatusBadge status={product.status.term} locale={locale} />}
    </div>
  );
};
