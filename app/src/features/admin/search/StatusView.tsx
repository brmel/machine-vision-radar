import { useState, type FC } from "react";
import type { IndexStatus } from "../../../domain/views.ts";
import { Button, Facts, PageHeader, formatDate, formatNumber } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { logger } from "../../../shell/logger.ts";
import { useAdmin } from "../model.ts";
import { useLoad } from "../useLoad.tsx";
import { IndexDetails } from "./IndexDetails.tsx";
import { WeekTable } from "./WeekTable.tsx";

export const StatusView: FC = () => {
  const { search } = useAdmin();
  const { t, locale } = useI18n();
  const status = useLoad(() => search.status(), "search-status");
  const [running, setRunning] = useState(false);
  const [ran, setRan] = useState<IndexStatus | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const run = (action: "update" | "rebuild") => () => {
    setRunning(true);
    setFailed(null);
    search.run(action).then(setRan, (err: unknown) => {
      logger.error(`admin: the index ${action} failed`, { page: "admin" }, err);
      setFailed(err instanceof Error ? err.message : String(err));
    }).finally(() => setRunning(false));
  };
  const shown = ran ?? status.value;
  if (status.failed || !shown) return status.pending;
  return (
    <section className="space-y-6">
      <PageHeader title={t("adminSearchTitle")} />
      <Facts layout="grid" className="text-body" facts={[
        { key: "version", label: t("versionField_label"),
          value: <span className="font-mono">{shown.version ?? "—"}</span> },
        { key: "products", label: t("adminSearchProducts"),
          value: t("adminSearchIndexed", { indexed: formatNumber(shown.products_indexed ?? 0, locale),
            catalog: formatNumber(shown.products_in_catalog, locale) }) },
        { key: "built", label: t("adminSearchBuilt"),
          value: shown.built_at ? formatDate(shown.built_at, locale) : "—" },
      ]} />
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={run("update")} disabled={running}>{t("adminSearchUpdate")}</Button>
        <Button variant="outline" onClick={run("rebuild")} disabled={running}>{t("adminSearchRebuild")}</Button>
        {running && <span role="status" className="text-caption text-muted">{t("adminSearchRunning")}</span>}
      </div>
      {failed && <p role="alert" className="text-caption text-danger break-words">{t("adminSearchRunFailed",
        { error: failed })}</p>}
      <IndexDetails status={shown} />
      <WeekTable />
    </section>
  );
};
