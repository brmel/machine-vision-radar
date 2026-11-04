import { useState, type ChangeEvent, type FC } from "react";
import type { CapChange } from "../../../../domain/ports/review/SearchAdmin.ts";
import type { AiCapRow, AiCaps } from "../../../../domain/views.ts";
import { Button, CONTROL, Field, Section, prevented } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { USE, useAdmin } from "../../model.ts";
import { usePaged, useProblem } from "../../useLoad.tsx";
import { CapHistory } from "./CapHistory.tsx";
import { CapLimits } from "./CapLimits.tsx";

const PATH = "/search/settings";

export const UseForm: FC<{ caps: AiCaps; use: AiCapRow["use"]; search: string; onSaved: () => void }> = ({ caps, use,
  search, onSaved }) => {
  const { search: admin, review, onNavigate } = useAdmin();
  const { t } = useI18n();
  const history = usePaged((cursor) => admin.capHistory(use, cursor), `cap-history-${use}`, PATH, search, 1);
  const [change, setChange] = useState<CapChange>({});
  const [reason, setReason] = useState("");
  const { alert, say, refuse } = useProblem("a cap change");
  const reload = () => {
    onSaved();
    history.reload();
    setChange({});
    setReason("");
    say([]);
  };
  const onUse = (event: ChangeEvent<HTMLSelectElement>) =>
    onNavigate(`${PATH}?${new URLSearchParams({ use: event.target.value })}`);
  const set = (key: keyof CapChange, value: string | number | undefined) =>
    setChange((c) => (value === undefined ? Object.fromEntries(Object.entries(c).filter(([k]) => k !== key))
      : { ...c, [key]: value }));
  const onModel = (event: ChangeEvent<HTMLSelectElement>) => set("model", event.target.value || undefined);
  const onLimit = (key: keyof CapChange) => (event: ChangeEvent<HTMLInputElement>) =>
    set(key, event.target.value === "" ? undefined : Number(event.target.value));
  const onReason = (event: ChangeEvent<HTMLTextAreaElement>) => setReason(event.target.value);
  const save = prevented(() => admin.setCap(use, change, reason.trim()).then(reload, refuse));
  const revert = (proposal: string) => () => {
    if (!reason.trim()) return say([t("adminCapsNeedReason")]);
    review.decide({ decision: "retract", target: { proposals: [proposal] }, note: reason.trim() }).then(reload, refuse);
  };
  const running = caps.models.find((m) => m.id === caps.uses.find((r) => r.use === use)?.model);
  return (
    <>
      <Section sub title={t("adminSettingsChange")} note={t("adminSettingsChangeWhat")}>
        <form onSubmit={save} className="space-y-3 max-w-2xl">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("adminCapsUse")}>
              <select className={CONTROL} value={use} onChange={onUse}>{caps.uses.map((r) =>
                <option key={r.use} value={r.use}>{t(USE[r.use])}</option>)}</select>
            </Field>
            {running && (
              <Field label={t("adminSettingsModel")}>
                <select className={CONTROL} value={change.model ?? ""} onChange={onModel}>
                  <option value="">{t("adminSettingsKeep", { model: running.label })}</option>
                  {caps.models.filter((m) => m !== running)
                    .map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
              </Field>
            )}
          </div>
          <CapLimits change={change} onLimit={onLimit} />
          <Field label={t("adminReason")}><textarea className={CONTROL} value={reason} onChange={onReason} required
            rows={2} /></Field>
          <Button type="submit" variant="primary" disabled={!reason.trim()}>{t("adminSettingsSave")}</Button>
          {alert}
        </form>
      </Section>
      <CapHistory use={use} history={history} onRevert={revert} />
    </>
  );
};
