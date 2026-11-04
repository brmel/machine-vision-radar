import { useState, type FC } from "react";
import type { IssuedToken } from "../../../domain/views.ts";
import { Button, Section } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useProblem } from "../useLoad.tsx";

export const NewToken: FC<{ issued: IssuedToken }> = ({ issued }) => {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const { alert, refuse: fail } = useProblem("copying a token");
  const copy = () => void navigator.clipboard.writeText(issued.token).then(() => setCopied(true), fail);
  return (
    <Section id="agents-issued" title={t("adminAgentsIssued", { name: issued.agent.name })}
      className="rounded-control border border-line p-3">
      <p className="text-caption">{t("adminAgentsShownOnce")}</p>
      <div className="flex flex-wrap items-center gap-2">
        <code className="font-mono text-caption break-all">{issued.token}</code>
        <Button variant="outline" size="sm" onClick={copy}>{t("adminAgentsCopy")}</Button>
      </div>
      {copied && <p role="status" className="text-caption text-muted">{t("adminAgentsCopied")}</p>}
      {alert}
    </Section>
  );
};
