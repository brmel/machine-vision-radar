import { type ReactNode, useState } from "react";
import { CELL, NUM, Pagination, Table } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { usePagerLabels } from "../../../shell/i18n/labels.ts";

const ROWS = 10;

interface Row {
  readonly key: string;
  readonly cells: readonly ReactNode[];
}

export function Counts({ label, heads, numbers, rows }: { label: string; heads: readonly string[];
  numbers: readonly number[]; rows: readonly Row[] }) {
  const { t } = useI18n();
  const pager = usePagerLabels();
  const [page, setPage] = useState(1);
  const align = (n: number) => (numbers.includes(n) ? NUM : "");
  return (
    <div className="space-y-3">
      <Table label={label} className="text-caption" columns={heads.map((head, n) => ({ head, className: align(n) }))}>
        {rows.slice((page - 1) * ROWS, page * ROWS).map((r) => (
          <tr key={r.key}>
            {r.cells.map((cell, n) => <td key={heads[n]} className={`${CELL} ${align(n)}`}>{cell}</td>)}
          </tr>
        ))}
      </Table>
      <Pagination page={page} pageSize={ROWS} totalCount={rows.length} onPageChange={setPage}
        {...pager} navLabel={t("paginationTableLabel", { table: label })}
        summaryText={(start, end, total) => t("paginationRows", { start, end, total })} />
    </div>
  );
}
