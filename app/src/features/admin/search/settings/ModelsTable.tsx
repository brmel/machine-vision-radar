import type { FC } from "react";
import type { AiCaps } from "../../../../domain/views.ts";
import { CELL, NUM, ROW_HEAD, formatDate, formatNumber } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { AdminTable } from "../AdminTable.tsx";

const COLUMNS = [["adminSettingsModel"], ["adminSettingsRegion"], ["adminSettingsPriceIn", "text-right"],
  ["adminSettingsPriceOut", "text-right"], ["adminSettingsPriceRead"]] as const;

export const ModelsTable: FC<{ caps: AiCaps }> = ({ caps }) => {
  const { t, locale } = useI18n();
  return (
    <>
      <AdminTable caption={t("adminSettingsModels")} columns={COLUMNS}>
        {caps.models.map((m) => (
          <tr key={m.id}>
            <th scope="row" className={ROW_HEAD}>
              {m.label} <span className="font-mono text-muted whitespace-nowrap">{m.id}</span>
            </th>
            <td className={`${CELL} font-mono whitespace-nowrap`}>
              {"vertex" in m.provider ? `vertex · ${m.provider.vertex}` : `meta · ${m.provider.meta}`}
            </td>
            <td className={`${CELL} ${NUM}`}>{formatNumber(m.usd_in, locale)}</td>
            <td className={`${CELL} ${NUM}`}>{formatNumber(m.usd_out, locale)}</td>
            <td className={`${CELL} whitespace-nowrap`}><a href={m.source} className="underline" target="_blank"
              rel="noreferrer">{formatDate(m.read, locale)}</a></td>
          </tr>
        ))}
      </AdminTable>
      <p className="text-caption text-muted max-w-3xl">{t("adminSettingsModelsWhat",
        { rate: formatNumber(caps.cad_per_usd, locale) })}</p>
    </>
  );
};
