import type { FC } from "react";
import type { ProductView } from "../../../domain/views.ts";
import { CELL, specRowLabel, specValueLang, useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { cellOf, leaders } from "../../../domain/compare.ts";
import { CompareTableRow } from "./CompareTableRow.tsx";
import { CompareValue } from "./CompareValue.tsx";

interface CompareSectionProps {
  section: "core" | "detail";
  keys: readonly string[];
  products: readonly ProductView[];
}

export const CompareSection: FC<CompareSectionProps> = ({ section, keys, products }) => {
  const { t, locale } = useI18n();
  const { spec_definitions: specDefs } = useRegistry();
  const row = (key: string) => {
    const best = leaders(products, key, specDefs[key].better);
    const value = (p: ProductView) => <CompareValue product={p} specKey={key} leads={best.has(p.id)} />;
    const lang = (p: ProductView) => specValueLang(cellOf(p, key).value, locale);
    return <CompareTableRow key={key} label={specRowLabel(key, specDefs, locale)} products={products} cell={value}
      lang={lang} />;
  };
  return (
    <>
      <tr className="bg-sunken">
        <th scope="colgroup" colSpan={products.length + 1} className={`${CELL} text-left font-semibold text-fg`}>
          {section === "core" ? t("specSectionCore") : t("specSectionDetail")}
        </th>
      </tr>
      {keys.map(row)}
    </>
  );
};
