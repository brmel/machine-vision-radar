import { useState, type ChangeEvent, type FC } from "react";
import type { ResearchScope } from "../../../domain/ports/review/agents/ResearchAdmin.ts";
import type { ResearchRunRow } from "../../../domain/views.ts";
import { Button, CONTROL, Field, PageHeader, Section, formatNumber } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import type { MessageKey } from "../../../shell/i18n/messages.ts";
import { useAdmin } from "../model.ts";
import { usePaged, useSubmit } from "../useLoad.tsx";
import { AdminTable } from "../search/AdminTable.tsx";
import { RunRow, WIDE } from "./RunRow.tsx";

const COLUMNS = [["adminResearchStarted"], ["adminResearchScope"], ["adminResearchPages", `text-left ${WIDE}`],
  ["adminResearchFiledCount"], ["adminResearchRejected", `text-left ${WIDE}`], ["adminResearchCost"]] as const;

const KINDS = { product: "adminResearchProduct", maker: "adminResearchMaker",
  category: "adminResearchCategory" } as const satisfies Readonly<Record<string, MessageKey>>;
type Kind = keyof typeof KINDS;
const isKind = (value: string): value is Kind => Object.hasOwn(KINDS, value);

const scopeOf = (kind: Kind, key: string): ResearchScope => {
  if (kind === "product") return { product: key };
  return kind === "maker" ? { maker: key } : { category: key };
};

export const ResearchView: FC<{ search: string }> = ({ search }) => {
  const { research, onNavigate } = useAdmin();
  const { t, locale } = useI18n();
  const runs = usePaged((cursor) => research.researchRuns(cursor), "research", "/research", search);
  const [kind, setKind] = useState<Kind>("maker");
  const [key, setKey] = useState("");
  const onKind = (event: ChangeEvent<HTMLSelectElement>) => {
    if (isKind(event.target.value)) setKind(event.target.value);
  };
  const onKey = (event: ChangeEvent<HTMLInputElement>) => setKey(event.target.value);
  const open = (run: Pick<ResearchRunRow, "id">) => onNavigate(`/research/runs/${encodeURIComponent(run.id)}`);
  const { busy: running, submit: start, alert } =
    useSubmit("a research run", () => research.startResearch(scopeOf(kind, key.trim())), open);
  return (
    <section className="space-y-6">
      <PageHeader title={t("adminResearchTitle")} />
      <form onSubmit={start} className="space-y-3 max-w-2xl">
        <div className="grid gap-3 sm:grid-cols-[minmax(10rem,auto)_1fr]">
          <Field label={t("adminResearchScope")}>
            <select className={CONTROL} value={kind} onChange={onKind}>
              {Object.entries(KINDS).map(([k, label]) => <option key={k} value={k}>{t(label)}</option>)}
            </select>
          </Field>
          <Field label={t("adminResearchKey")}><input className={CONTROL} value={key} onChange={onKey} required
            aria-describedby="research-scope-hint" /></Field>
        </div>
        <p id="research-scope-hint" className="text-caption text-muted">{t("adminResearchScopeHint")}</p>
        <Button type="submit" variant="primary" disabled={running || !key.trim()}>{t("adminResearchRunNow")}</Button>
        {running && <p role="status" className="text-caption text-muted">{t("adminResearchInProgress")}</p>}
        {alert}
      </form>
      {!runs.value ? runs.pending : (
        <Section id="research-runs" title={t("adminResearchRuns", { count: formatNumber(runs.value.total, locale) })}>
          {runs.value.runs.length === 0 ? <p className="text-caption text-muted">{t("adminResearchNone")}</p> : (
            <AdminTable columns={COLUMNS}>
              {runs.value.runs.map((run) => <RunRow key={run.id} run={run} />)}
            </AdminTable>
          )}
          {runs.pager}
        </Section>
      )}
    </section>
  );
};
