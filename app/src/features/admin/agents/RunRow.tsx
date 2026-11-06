import type { FC } from "react";
import type { ResearchRunRow } from "../../../domain/views.ts";
import { Badge, CELL, ROW_HEAD, formatInstant, formatNumber } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { RUN_SCOPE, RUN_STATUS } from "../model.ts";
import { AdminLink } from "../useLoad.tsx";

export const WIDE = "hidden sm:table-cell";

export const RunRow: FC<{ run: ResearchRunRow }> = ({ run }) => {
  const { t, locale } = useI18n();
  const [status, tone] = RUN_STATUS[run.status];
  return (
    <tr>
      <th scope="row" className={ROW_HEAD}>
        <AdminLink to={`/research/runs/${encodeURIComponent(run.id)}`} className="underline">
          <time dateTime={run.started_at}>{formatInstant(run.started_at, locale)}</time>
        </AdminLink>
        <span className="block mt-1"><Badge tone={tone}>{t(status)}</Badge></span>
      </th>
      <td className={`${CELL} break-words`}>{t(RUN_SCOPE[run.scope.kind])} · {run.scope.key}</td>
      <td className={`${CELL} tabular-nums ${WIDE}`}>{formatNumber(run.pages, locale)}</td>
      <td className={`${CELL} tabular-nums`}>{formatNumber(run.filed, locale)}</td>
      <td className={`${CELL} tabular-nums ${WIDE}`}>{formatNumber(run.rejected, locale)}</td>
      <td className={`${CELL} tabular-nums`}>{t("adminResearchCad", { cad: formatNumber(run.cad, locale) })}</td>
    </tr>
  );
};
