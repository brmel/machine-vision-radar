import type { FC, ReactNode } from "react";
import type { ProductView } from "../../../domain/views.ts";
import { CELL, ROW_HEAD } from "../../../ui/index.ts";

export const STICKY = "max-sm:sr-only sm:sticky sm:left-0 sm:z-10 sm:w-44";

interface CompareTableRowProps {
  label: string;
  products: readonly ProductView[];
  cell: (product: ProductView) => ReactNode;
  lang?: (product: ProductView) => string | undefined;
}

export const CompareTableRow: FC<CompareTableRowProps> = ({ label, products, cell, lang }) => (<>
  <tr aria-hidden="true" className="sm:hidden border-b-0">
    <td colSpan={products.length} className={`${ROW_HEAD} max-sm:px-1.5 pb-0`}>{label}</td>
  </tr>
  <tr className="hover:bg-sunken/60">
    <th scope="row" className={`${ROW_HEAD} ${STICKY} bg-surface`}>{label}</th>
    {products.map((p) => (
      <td key={p.id} lang={lang?.(p)} className={`${CELL} max-sm:px-1.5 tabular-nums text-fg`}>{cell(p)}</td>
    ))}
  </tr>
</>);
