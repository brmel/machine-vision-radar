import { type FC } from "react";
import type { FieldChangeView } from "../../../domain/views.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { CELL, ROW_HEAD, Table } from "../../../ui/index.ts";

export const DiffTable: FC<{ title?: string; heads: readonly [string, string];
  rows: readonly FieldChangeView[] }> = ({ title, heads, rows }) => {
  const { t } = useI18n();
  return (
    <div className="space-y-1">
      {title && <p className="text-caption font-mono text-fg-secondary break-all">{title}</p>}
      <Table className="text-caption" columns={[{ head: t("adminDiffField") }, { head: heads[0] }, { head: heads[1] }]}>
        {rows.map((r) => (
          <tr key={r.path}>
            <th scope="row" className={`${ROW_HEAD} font-mono break-all`}>{r.path}</th>
            <td className={`${CELL} font-mono break-all text-danger`}>{r.before ?? "—"}</td>
            <td className={`${CELL} font-mono break-all text-success`}>{r.after ?? "—"}</td>
          </tr>
        ))}
      </Table>
    </div>
  );
};
