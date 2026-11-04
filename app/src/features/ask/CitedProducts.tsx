import { type FC } from "react";
import { productPath } from "../../domain/paths.ts";
import type { Citation, ProductView } from "../../domain/views.ts";
import { AppLink, SourceChip } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";

interface CitedProductsProps {
  citations: readonly Citation[];
  cited: ReadonlyMap<string, ProductView>;
  onSelectProduct: (slug: string) => void;
  label?: string;
}

export const CitedProducts: FC<CitedProductsProps> = ({ citations, cited, onSelectProduct, label }) => {
  const { locale } = useI18n();
  return (
    <ul aria-label={label} className="space-y-1.5">
      {citations.map((c) => {
        const view = cited.get(c.product);
        const source = c.source ? view?.sources.find((s) => s.id === c.source) : undefined;
        return view ? (
          <li key={`${c.product}-${c.source ?? ""}`} className="flex flex-wrap items-center gap-2 text-caption">
            <AppLink href={productPath(view.slug)} onOpen={() => onSelectProduct(view.slug)}
              className="font-medium underline text-fg">{view.name}</AppLink>
            {source && <SourceChip source={source} locale={locale} />}
          </li>
        ) : null;
      })}
    </ul>
  );
};
