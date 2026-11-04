import { useState, type ChangeEvent, type FC } from "react";
import type { TokenRequest } from "../../../domain/ports/review/agents/AgentsAdmin.ts";
import type { AgentLimits, AgentTokenView, IssuedToken } from "../../../domain/views.ts";
import { Button, CONTROL, Field, Section } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { SCOPE, useAdmin } from "../model.ts";
import { useSubmit } from "../useLoad.tsx";

const LIMITS = [["requests_per_minute", "adminAgentsRequests"], ["proposals_per_day", "adminAgentsProposals"]] as const;

export const IssueForm: FC<{ limits: AgentLimits;
  onIssued: (issued: IssuedToken) => void }> = ({ limits, onIssued }) => {
  const { agents } = useAdmin();
  const { t } = useI18n();
  const [request, setRequest] = useState<TokenRequest>({ name: "", scope: "read", expires: "", limits });
  const onName = (event: ChangeEvent<HTMLInputElement>) => setRequest((r) => ({ ...r, name: event.target.value }));
  const onExpires = (event: ChangeEvent<HTMLInputElement>) =>
    setRequest((r) => ({ ...r, expires: event.target.value }));
  const onScope = (event: ChangeEvent<HTMLSelectElement>) => {
    const scope = Object.keys(SCOPE).find((s): s is AgentTokenView["scope"] => s === event.target.value);
    if (scope) setRequest((r) => ({ ...r, scope }));
  };
  const onLimit = (key: keyof AgentLimits) => (event: ChangeEvent<HTMLInputElement>) =>
    setRequest((r) => ({ ...r, limits: { ...r.limits, [key]: Number(event.target.value) } }));
  const { submit: issue, alert } =
    useSubmit("an agent token", () => agents.issueToken({ ...request, name: request.name.trim() }), onIssued);
  return (
    <Section title={t("adminAgentsIssueTitle")}>
      <form onSubmit={issue} className="space-y-3 max-w-2xl">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label={t("adminAgentsName")}><input className={CONTROL} value={request.name} onChange={onName}
            required /></Field>
          <Field label={t("adminAgentsScope")}>
            <select className={CONTROL} value={request.scope} onChange={onScope}>
              {Object.entries(SCOPE).map(([scope, words]) => <option key={scope} value={scope}>{t(words)}</option>)}
            </select>
          </Field>
          <Field label={t("adminAgentsExpires")}><input className={CONTROL} type="date" value={request.expires}
            onChange={onExpires} required /></Field>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {LIMITS.map(([key, words]) => (
            <Field key={key} label={t(words)}>
              <input className={CONTROL} type="number" min={1} step={1} value={request.limits[key]}
                onChange={onLimit(key)} required />
            </Field>
          ))}
        </div>
        <Button type="submit" variant="primary"
          disabled={!request.name.trim() || !request.expires}>{t("adminAgentsIssue")}</Button>
        {alert}
      </form>
    </Section>
  );
};
