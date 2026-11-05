import type { FC } from "react";
import { CELL, NUM, ROW_HEAD, Section, formatDate, formatNumber } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useAdmin } from "../model.ts";
import { useLoad } from "../useLoad.tsx";
import { AdminTable } from "./AdminTable.tsx";

const COUNTS = [
  ["search", "adminCountSearches"], ["zero_result", "adminCountZero"], ["result_click", "adminCountClicks"],
  ["answer", "adminCountAnswers"], ["refusal", "adminCountRefusals"],
] as const;

export const WeekTable: FC = () => {
  const { search } = useAdmin();
  const { t, locale } = useI18n();
  const weekly = useLoad(() => search.weekly(), "search-weekly", 2, 2);
  const table = weekly.value && (
    <AdminTable columns={[["adminSearchWeek"], ...COUNTS.map(([, label]) => [label, "text-right"] as const)]}>
      {weekly.value.weeks.map((w) => (
        <tr key={w.week}>
          <th scope="row" className={ROW_HEAD}>{formatDate(w.week, locale)}</th>
          {COUNTS.map(([key]) =>
            <td key={key} className={`${CELL} ${NUM}`}>{formatNumber(w.counts[key] ?? 0, locale)}</td>)}
        </tr>
      ))}
    </AdminTable>
  );
  return (
    <Section title={t("adminSearchWeekly")}>
      {table || weekly.pending}
    </Section>
  );
};
