import { useState, type FC } from "react";
import { Badge, Button, PageHeader, RowList, Section, formatInstant, formatNumber } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { RUN_STATUS, STEP, useAdmin } from "../model.ts";
import { AdminLink, Pager, pageRows, useProblem, useLoad } from "../useLoad.tsx";

export const RunPage: FC<{ id: string }> = ({ id }) => {
  const { research } = useAdmin();
  const { t, locale } = useI18n();
  const run = useLoad(() => research.researchRun(id), `research/${id}`);
  const { alert, refuse: fail } = useProblem("cancelling a research run");
  const [page, setPage] = useState(1);
  const cancel = () => void research.cancelResearch(id).then(run.reload, fail);
  if (!run.value) return run.pending;
  const { scope, status, started_at: started, ended_at: ended, actor, cad, filed, media, datasheets, lines } =
    run.value;
  const [said, tone] = RUN_STATUS[status];
  return (
    <article className="space-y-6">
      <PageHeader title={t("adminResearchRunTitle", { scope })} actions={status === "running"
        && <Button variant="outline" onClick={cancel}>{t("adminResearchCancel")}</Button>}>
        <p className="text-caption text-muted">
          <Badge tone={tone}>{t(said)}</Badge> · <time dateTime={started}>{formatInstant(started, locale)}</time>
          {ended && <> · {t("adminEnded", { at: formatInstant(ended, locale) })}</>} · {actor} · {t("adminResearchCad",
            { cad: formatNumber(cad, locale) })}
        </p>
        <p className="font-mono text-micro text-muted break-all">{id}</p>
      </PageHeader>
      {alert}
      <Section id="run-filed" title={t("adminResearchFiled", { count: formatNumber(filed.length, locale) })}>
        <p className="text-caption text-muted">{t("adminResearchFiles",
          { media: formatNumber(media.length, locale), datasheets: formatNumber(datasheets.length, locale) })}</p>
        {filed.length > 0 && (
          <p className="text-body"><AdminLink to={`/queue/bundles/${id}`}
            className="underline">{t("adminResearchBundle")}</AdminLink></p>
        )}
        {filed.length === 0 ? <p className="text-caption text-muted">{t("adminResearchNoneFiled")}</p> : (
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-caption">
            {filed.map((p) => (
              <li key={p}><AdminLink to={`/queue/${p}`} className="font-mono underline">{p}</AdminLink></li>
            ))}
          </ul>
        )}
      </Section>
      <Section id="run-log" title={t("adminResearchLog")}>
        <RowList ordered>
          {pageRows(lines, page).map((line, n) => (
            <li key={`${page}-${n}`} className="p-2 text-caption flex flex-wrap gap-x-3">
              <time dateTime={line.at} className="tabular-nums text-muted">{formatInstant(line.at, locale)}</time>
              <span className="font-medium">{t(STEP[line.step])}</span>
              <span className="break-all">{line.detail}</span>
            </li>
          ))}
        </RowList>
        <Pager page={page} total={lines.length} onPage={setPage} />
      </Section>
    </article>
  );
};
