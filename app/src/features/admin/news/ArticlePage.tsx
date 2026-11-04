import type { FC } from "react";
import { articlePath } from "../../../domain/paths.ts";
import { PageHeader, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useAdmin } from "../model.ts";
import { useLoad } from "../useLoad.tsx";
import { Decision } from "../queue/Decision.tsx";
import { ArticleForm } from "./ArticleForm.tsx";
import { ShareActions } from "./ShareActions.tsx";

export const ArticlePage: FC<{ id: string }> = ({ id }) => {
  const { news, onNavigate } = useAdmin();
  const { t, locale } = useI18n();
  const isNew = id === "new";
  const loaded = useLoad(() => (isNew ? Promise.resolve(null) : news.article(id)), `news/${id}`);
  const onDone = () => onNavigate("/news");
  if (isNew) return <section className="space-y-4"><PageHeader title={t("adminNewsWrite")} /><ArticleForm
    onSaved={onDone} /></section>;
  if (!loaded.value) return loaded.pending;
  const row = loaded.value;
  const retract = (note: string) => news.retractArticle(row.id, note).then(onDone);
  return (
    <section className="space-y-6">
      <PageHeader title={localized(row.title, locale)} />
      {row.published_at && (
        <div className="space-y-2">
          <p className="text-caption font-mono"><a href={articlePath(row.slug)}
            className="underline">{articlePath(row.slug)}</a></p>
          <ShareActions row={row} />
        </div>
      )}
      <ArticleForm row={row} onSaved={onDone} />
      {row.published_at && <Decision noteLabel={t("adminNewsRetractNote")}
        actions={[{ label: t("adminNewsRetract"), run: retract }]} />}
    </section>
  );
};
