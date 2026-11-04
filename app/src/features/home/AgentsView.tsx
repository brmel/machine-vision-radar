import type { FC } from "react";
import { PageHeader, Section } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { SITE_ORIGIN } from "../../shell/seo/siteOrigin.ts";
import { mcpClients, mcpEndpoint } from "./copy.ts";

const CODE =
  "p-3 bg-sunken rounded-control border border-line font-mono text-caption text-fg whitespace-pre-wrap wrap-anywhere";

export const AgentsView: FC = () => {
  const { t } = useI18n();
  return (
    <div className="max-w-3xl space-y-4">
      <PageHeader title={t("agentsTitle")} lead={t("agentsDescription")} />
      <Section title={t("agentsEndpointTitle")} note={t("agentsEndpointDesc")}>
        <p className={`${CODE} select-all`}>{mcpEndpoint(SITE_ORIGIN)}</p>
        <p className="text-caption text-muted">{t("agentsAuthDesc")}</p>
      </Section>
      {mcpClients(SITE_ORIGIN).map(([name, snippet]) => (
        <Section key={name} title={t(name)}>
          <pre className={CODE}><code>{snippet}</code></pre>
        </Section>
      ))}
    </div>
  );
};
