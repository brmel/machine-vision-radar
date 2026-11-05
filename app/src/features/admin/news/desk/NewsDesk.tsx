import type { FC } from "react";
import type { FeedDeskRow } from "../../../../domain/views.ts";
import { Button, PageHeader, Section, formatDate } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { useAdmin } from "../../model.ts";
import { useProblem, usePaged } from "../../useLoad.tsx";
import { Decision } from "../../queue/Decision.tsx";
import { AiDraft } from "../AiDraft.tsx";
import { DeskLink } from "./DeskLink.tsx";
import { DraftList } from "./DraftList.tsx";

export const NewsDesk: FC<{ search: string }> = ({ search }) => {
  const { news, onNavigate } = useAdmin();
  const { t, locale } = useI18n();
  const desk = usePaged((cursor) => news.newsDesk(cursor), "news", "/news", search);
  const { alert, refuse: fail } = useProblem("moving a draft");
  if (!desk.value) return desk.pending;
  const { drafts, published } = desk.value;

  const move = (row: FeedDeskRow, position: number) => () => void news.moveDraft(row.id, position)
    .then(desk.reload, fail);
  const publish = (note: string) => news.publishNext(note).then(desk.reload);
  const templated = (note: string) => news.publishTemplated(note).then(desk.reload);
  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHeader title={t("adminNavNews")} />
        <Button variant="primary" onClick={() => onNavigate("/news/new")}>{t("adminNewsWrite")}</Button>
      </div>
      <Section id="news-drafts" title={t("adminNewsDrafts")}>
        <AiDraft onDrafted={desk.reload} />
        {drafts.length === 0 && <p className="text-caption text-muted">{t("adminNewsNoDraft")}</p>}
        <DraftList drafts={drafts} onMove={move} />
        {alert}
        {drafts.length > 0 && (
          <Decision actions={[
            { label: t("adminNewsPublishNext"), run: publish, primary: true },
            ...(drafts.some((d) => d.authorship === "template")
              ? [{ label: t("adminNewsApproveTemplated"), run: templated }] : []),
          ]} />
        )}
      </Section>
      <Section id="news-published" title={t("adminNewsPublished")} aside={desk.count}>
        {published.length === 0 && <p className="text-caption text-muted">{t("adminNewsNothingPublished")}</p>}
        <ul className="divide-y divide-line">
          {published.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center gap-2 py-2">
              <DeskLink row={row} />
              {row.published_at
                && <time dateTime={row.published_at} className="text-caption text-muted">{formatDate(row.published_at,
                  locale)}</time>}
            </li>
          ))}
        </ul>
        {desk.pager}
      </Section>
    </section>
  );
};
