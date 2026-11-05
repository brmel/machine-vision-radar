import { useState, type FC } from "react";
import type { ProductView } from "../../../domain/views.ts";
import { productPath } from "../../../domain/paths.ts";
import { AppLink, CELL, Section, Table, formatSpecValueText, specRowLabel, useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useValueLabels } from "../../../shell/i18n/labels.ts";

const FIRST_MODELS = 20;

export const FamilyModels: FC<{ product: ProductView; onSelectProduct: (slug: string) => void }> = ({ product,
  onSelectProduct }) => {
  const { t, locale } = useI18n();
  const { spec_definitions: specDefs } = useRegistry();
  const labels = useValueLabels();
  const [open, setOpen] = useState(false);
  const shown = open ? product.models : product.models.slice(0, FIRST_MODELS);
  return (
    <Section title={t("familyModelsTitle")} className="models">
      <Table columns={[{ head: t("familyModelsTitle") },
        ...product.core.map((c) => ({ head: specRowLabel(c.key, specDefs, locale) }))]}>
        {shown.map((m) => (
          <tr key={m.id}>
            <th scope="row" className={`${CELL} text-left font-medium`}>
              <AppLink href={productPath(m.slug)} onOpen={() => onSelectProduct(m.slug)}
                className="underline">{m.name}</AppLink>
            </th>
            {m.specs.map((c) => (
              <td key={c.key} className={`${CELL} tabular-nums ${c.value === undefined ? "italic text-muted" : ""}`}>
                {formatSpecValueText(c.value, labels, "label")}
              </td>
            ))}
          </tr>
        ))}
      </Table>
      {product.models.length > FIRST_MODELS && (
        <button type="button" aria-expanded={open} onClick={() => setOpen((was) => !was)}
          className="mt-2 text-caption text-muted underline cursor-pointer hover:text-fg">
          {open ? t("facetFewer") : t("moreCount", { count: product.models.length - FIRST_MODELS })}
        </button>
      )}
    </Section>
  );
};
