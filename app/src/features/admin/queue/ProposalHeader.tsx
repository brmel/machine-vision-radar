import { type FC } from "react";
import type { ProposalView } from "../../../domain/views.ts";
import { PageHeader, formatDate } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { ACTOR, STATUS, kindLabel, recordPath, useAdmin } from "../model.ts";
import { AdminLink } from "../useLoad.tsx";

export const ProposalHeader: FC<{ proposal: ProposalView }> = ({ proposal: p }) => {
  const { model } = useAdmin();
  const { t, locale } = useI18n();
  const subject = p.subject ? recordPath(model, p.subject) : null;
  return (
    <PageHeader title={`${kindLabel(model, p.files_on, locale)}: ${p.reason || p.message}`}>
      <p className="text-caption text-muted">
        {t(STATUS[p.status])} · {p.author} ({t(ACTOR[p.actor_kind])}) · {formatDate(p.created_at, locale)} · <span
          className="font-mono">{p.id}</span>
      </p>
      {p.subject && (
        <p className="text-body">
          {t("adminSubject")}: {subject ? <AdminLink to={subject}
            className="font-mono underline">{p.subject}</AdminLink> : <span className="font-mono">{p.subject}</span>}
        </p>
      )}
      {p.reviewer && <p className="text-body">{t("adminDecided", { reviewer: p.reviewer, note: p.note ?? "" })}</p>}
      {p.message && <blockquote
        className="border-l-4 border-line-strong pl-3 text-body break-words">{p.message}</blockquote>}
      {p.source_url && <p className="text-body break-all"><a className="underline" href={p.source_url}
        rel="noopener noreferrer" target="_blank">{p.source_url}</a></p>}
      {p.problem && <p role="alert" className="text-body text-warning">{p.problem}</p>}
    </PageHeader>
  );
};
