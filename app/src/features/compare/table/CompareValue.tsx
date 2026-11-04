import type { FC } from "react";
import type { ProductView } from "../../../domain/views.ts";
import { Badge, SourceChip, formatSpecValueText, useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useValueLabels } from "../../../shell/i18n/labels.ts";
import { cellOf } from "../../../domain/compare.ts";

export const CompareValue: FC<{ product: ProductView; specKey: string;
  leads: boolean }> = ({ product, specKey, leads }) => {
  const { t, locale } = useI18n();
  const { spec_definitions: specDefs } = useRegistry();
  const labels = useValueLabels();
  const cell = cellOf(product, specKey);
  const source = cell.source === undefined ? undefined : product.sources.find((s) => s.id === cell.source);
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span className={cell.value === undefined ? "italic text-muted" : leads ? "font-semibold"
        : ""}>{formatSpecValueText(cell.value, labels, "label")}</span>
      {leads && <Badge
        tone="accent">{t(specDefs[specKey].better === "higher" ? "compareHighest" : "compareLowest")}</Badge>}
      {source && <SourceChip source={source} locale={locale} />}
    </span>
  );
};
