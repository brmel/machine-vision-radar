import { useState, type FC } from "react";
import type { AgentTokenView } from "../../../domain/views.ts";
import type { MessageKey } from "../../../shell/i18n/messages.ts";
import { Badge, Button, CELL, ROW_HEAD, formatDate, formatNumber } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { SCOPE, useAdmin } from "../model.ts";
import { useProblem } from "../useLoad.tsx";

const STATUS = {
  active: ["adminAgentsActive", "positive"], expired: ["adminAgentsExpired", "warning"],
  revoked: ["adminAgentsRevoked", "neutral"],
} as const satisfies Readonly<Record<AgentTokenView["status"], readonly [MessageKey, string]>>;

export const TokenRow: FC<{ token: AgentTokenView; onRevoked: () => void }> = ({ token, onRevoked }) => {
  const { agents } = useAdmin();
  const { t, locale } = useI18n();
  const [confirming, setConfirming] = useState(false);
  const { alert, refuse: fail } = useProblem("revoking a token");
  const ask = () => setConfirming(true);
  const keep = () => setConfirming(false);
  const revoke = () => void agents.revokeToken(token.id).then(onRevoked, fail);
  const [status, tone] = STATUS[token.status];
  const limits = { requests: formatNumber(token.limits.requests_per_minute, locale),
    proposals: formatNumber(token.limits.proposals_per_day, locale) };
  return (
    <tr>
      <th scope="row" className={`${ROW_HEAD} break-words`}>
        {token.name}
        <span className="block font-mono text-micro text-muted">{token.id}</span>
      </th>
      <td className={CELL}>
        {t(SCOPE[token.scope])}
        <span className="block text-muted tabular-nums">{t("adminAgentsLimitsOf", limits)}</span>
      </td>
      <td className={`${CELL} tabular-nums`}>{formatDate(token.expires, locale)}</td>
      <td className={`${CELL} space-y-1`}>
        <Badge tone={tone}>{t(status)}</Badge>
        {token.status !== "revoked" && !confirming && (
          <Button variant="outline" size="sm" onClick={ask}
            aria-label={t("adminAgentsRevokeName", { name: token.name })}>{t("adminAgentsRevoke")}</Button>
        )}
        {confirming && (
          <div role="group" aria-label={t("adminAgentsRevokeName", { name: token.name })} className="space-y-1">
            <p>{t("adminAgentsRevokeConfirm", { name: token.name })}</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" size="sm" onClick={revoke}>{t("adminAgentsRevokeYes")}</Button>
              <Button variant="ghost" size="sm" onClick={keep}>{t("adminAgentsKeep")}</Button>
            </div>
          </div>
        )}
        {alert}
      </td>
    </tr>
  );
};
