import type { FC } from "react";
import type { AiCaps } from "../../../../domain/views.ts";
import { CELL, NUM, ROW_HEAD, formatDate, formatNumber } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { USE } from "../../model.ts";
import { AdminTable } from "../AdminTable.tsx";

const COLUMNS = [["adminCapsUse"], ["adminSettingsModel"], ["adminSettingsPrompt"], ["adminCapsSpent", "text-right"],
  ["adminCapsCalls", "text-right"], ["adminCapsClient", "text-right"]] as const;

export const UsesTable: FC<{ caps: AiCaps }> = ({ caps }) => {
  const { t, locale } = useI18n();
  const label = (model?: string) => caps.models.find((m) => m.id === model)?.label ?? model ?? "—";
  return (
    <>
      <AdminTable caption={t("adminCapsDayOf", { day: formatDate(caps.day, locale) })} columns={COLUMNS}>
        {caps.uses.map((r) => (
          <tr key={r.use}>
            <th scope="row" className={ROW_HEAD}>{t(USE[r.use])}</th>
            <td className={CELL}>{label(r.model)}</td>
            <td className={`${CELL} font-mono whitespace-nowrap`}>{r.prompt ? `${r.prompt}.md` : "—"}</td>
            <td className={`${CELL} ${NUM}`}>{t("adminCapsOf",
              { used: formatNumber(r.cad_month, locale), cap: formatNumber(r.month_cad, locale) })}</td>
            <td className={`${CELL} ${NUM}`}>{t("adminCapsOf",
              { used: formatNumber(r.calls_today, locale), cap: formatNumber(r.day_calls, locale) })}</td>
            <td className={`${CELL} ${NUM}`}>{r.client_calls === undefined ? "—"
              : formatNumber(r.client_calls, locale)}</td>
          </tr>
        ))}
      </AdminTable>
      <ul className="text-caption text-muted space-y-1 max-w-3xl">
        {(["adminSettingsModelWhat", "adminSettingsPromptWhat", "adminSettingsCapsWhat"] as const)
          .map((key) => <li key={key}>{t(key)}</li>)}
      </ul>
    </>
  );
};
