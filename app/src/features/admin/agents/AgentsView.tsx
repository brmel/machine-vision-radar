import { useState, type FC } from "react";
import type { IssuedToken } from "../../../domain/views.ts";
import { PageHeader, Section, formatNumber } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useAdmin } from "../model.ts";
import { usePaged } from "../useLoad.tsx";
import { IssueForm } from "./IssueForm.tsx";
import { NewToken } from "./NewToken.tsx";
import { TokenRow } from "./TokenRow.tsx";
import { AdminTable } from "../search/AdminTable.tsx";

const COLUMNS = [["adminAgentsName"], ["adminAgentsScope"], ["adminAgentsExpires"], ["adminAgentsStatus"]] as const;

export const AgentsView: FC<{ search: string }> = ({ search }) => {
  const { agents } = useAdmin();
  const { t, locale } = useI18n();
  const listed = usePaged((cursor) => agents.agentTokens(cursor), "agents", "/agents", search);
  const [issued, setIssued] = useState<IssuedToken | null>(null);
  const onIssued = (found: IssuedToken) => {
    setIssued(found);
    listed.reload();
  };
  return (
    <section className="space-y-6">
      <PageHeader title={t("adminAgentsTitle")} />
      {issued && <NewToken issued={issued} />}
      {!listed.value ? listed.pending : (
        <>
          <IssueForm limits={listed.value.limits} onIssued={onIssued} />
          <Section id="agents-tokens"
            title={t("adminAgentsTokens", { count: formatNumber(listed.value.total, locale) })}>
            {listed.value.tokens.length === 0 ? <p className="text-caption text-muted">{t("adminAgentsNone")}</p> : (
              <AdminTable columns={COLUMNS}>
                {listed.value.tokens.map((token) =>
                  <TokenRow key={token.id} token={token} onRevoked={listed.reload} />)}
              </AdminTable>
            )}
            {listed.pager}
          </Section>
        </>
      )}
    </section>
  );
};
