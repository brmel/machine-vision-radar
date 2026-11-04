import { useState, type ChangeEvent, type FC } from "react";
import type { FieldDiff } from "../../../domain/views.ts";
import { Button, CONTROL, Field, RowList, Section, formatDate } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { ACTOR, useAdmin } from "../model.ts";
import { useProblem, usePaged } from "../useLoad.tsx";
import { Decision } from "../queue/Decision.tsx";
import { DiffTable } from "../queue/DiffTable.tsx";

export const HistoryTab: FC<{ id: string; search: string; onFiled: (proposal: string) => void }> = ({ id, search,
  onFiled }) => {
  const { editor, review } = useAdmin();
  const { t, locale } = useI18n();
  const [pair, setPair] = useState<{ from: number; to: number } | null>(null);
  const [diff, setDiff] = useState<FieldDiff | null>(null);
  const [target, setTarget] = useState<number | null>(null);
  const history = usePaged((cursor) => editor.history(id, cursor), `history/${id}`, `/records/${id}/history`, search);
  const { alert, refuse: fail } = useProblem("a diff read");
  if (!history.value) return history.pending;
  const { versions, total: latest } = history.value;
  const pickTarget = (version: number) => () => setTarget(version);
  const chosen = pair ?? { from: Math.max(1, latest - 1), to: latest };
  const choose = (end: "from" | "to") => (event: ChangeEvent<HTMLSelectElement>) =>
    setPair({ ...chosen, [end]: Number(event.target.value) });
  const compare = () => void editor.diff(id, chosen.from, chosen.to).then(setDiff, fail);
  const rollback = (reason: string) => (target ? review.submit({ filesOn: "rollback", subject: id, to: target, reason })
    .then((p) => onFiled(p.id)) : Promise.resolve());
  const pick = (end: "from" | "to") => (
    <Field label={end === "from" ? t("adminDiffFrom") : t("adminDiffTo")}>
      <select className={CONTROL} value={chosen[end]} onChange={choose(end)}>
        {Array.from({ length: latest }, (_, n) => latest - n).map((v) => <option key={v} value={v}>v{v}</option>)}
      </select>
    </Field>
  );
  return (
    <Section title={t("adminHistory")}>
      <RowList ordered>
        {versions.map((v) => (
          <li key={v.version} className="p-3 space-y-1">
            <p className="text-body"><span
              className="font-mono font-semibold">v{v.version}</span> · {formatDate(v.recorded_at,
                locale)} · {v.actor} ({t(ACTOR[v.actor_kind])})</p>
            <p className="text-caption break-words">{v.reason}</p>
            <p className="text-caption text-muted font-mono break-all">{v.changed.map((c) => c.path).join(", ")}</p>
            {v.version !== latest
              && <Button size="sm" variant="outline" onClick={pickTarget(v.version)}>{t("adminRollbackTo",
                { version: v.version })}</Button>}
          </li>
        ))}
      </RowList>
      {history.pager}
      {target !== null && <Decision noteLabel={t("adminReason")}
        actions={[{ label: t("adminRollbackTo", { version: target }), run: rollback, primary: true }]} />}
      {latest > 1 && (
        <div className="flex flex-wrap items-end gap-3">
          {pick("from")}
          {pick("to")}
          <Button variant="outline" onClick={compare}>{t("adminCompare")}</Button>
        </div>
      )}
      {alert}
      {diff && (
        <DiffTable heads={[`v${chosen.from}`, `v${chosen.to}`]} rows={diff.changes} />
      )}
    </Section>
  );
};
