import { type FC } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import type { ColumnSort } from "../../../domain/filtering/filterUrl.ts";
import type { CategoryEntry, ProductCard } from "../../../domain/views.ts";
import { productPath } from "../../../domain/paths.ts";
import { AppLink, CELL, Table, formatSpecValueText, localized, specRowLabel, useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useValueLabels } from "../../../shell/i18n/labels.ts";

interface ResultsTableProps {
  products: readonly ProductCard[];
  hub: CategoryEntry;
  column: ColumnSort | null;
  onSort: (key: string) => void;
  onSelectProduct: (slug: string) => void;
}

export const ResultsTable: FC<ResultsTableProps> = ({ products, hub, column, onSort, onSelectProduct }) => {
  const { spec_definitions: specs } = useRegistry();
  const { t, locale } = useI18n();
  const valueLabels = useValueLabels();
  const columns = hub.sections.core;
  const sortOf = (key: string): "ascending" | "descending"
    | "none" => (column?.key === key ? (column.desc ? "descending" : "ascending") : "none");
  const Arrow = column?.desc ? ArrowDown : ArrowUp;
  const heads = [
    { head: t("tableName") },
    { head: t("tableVendor") },
    ...columns.map((key) => ({
      sort: sortOf(key),
      head: (
        <button type="button" onClick={() => onSort(key)}
          className="inline-flex items-center gap-1 whitespace-nowrap hover:underline cursor-pointer">
          {specRowLabel(key, specs, valueLabels.locale)}
          {column?.key === key && <Arrow className="w-3 h-3" aria-hidden="true" />}
        </button>
      ),
    })),
  ];
  return (
    <Table label={localized(hub.label, locale)} columns={heads} className="text-caption">
      {products.map((p) => (
        <tr key={p.id}>
          <th scope="row" className={`${CELL} text-left font-medium`}>
            <AppLink href={productPath(p.slug)} onOpen={() => onSelectProduct(p.slug)}
              className="underline text-fg">{p.name}</AppLink>
          </th>
          <td className={`${CELL} text-fg-secondary`}>{p.vendor_name}</td>
          {columns.map((key) => (
            <td key={key}
              className={`${CELL} tabular-nums text-fg whitespace-nowrap`}>{formatSpecValueText(p.specs[key],
                valueLabels)}</td>
          ))}
        </tr>
      ))}
    </Table>
  );
};
