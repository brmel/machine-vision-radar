import { useMemo, type FC } from "react";
import type { CatalogRepository } from "../../../domain/ports/CatalogRepository.ts";
import { Badge, Breadcrumbs, Facts, PageHeader, SourceChip, formatDate, formatPartialDate, localized,
  useRead } from "../../../ui/index.ts";
import { NEWS_PATH } from "../../../domain/paths.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { DetailState } from "../../../shell/layout/DetailState.tsx";
import { buildArticleHeadMeta } from "../../../shell/seo/news.ts";
import { useRecordHead } from "../../../shell/seo/documentHead.ts";
import { SITE_ORIGIN } from "../../../shell/seo/siteOrigin.ts";
import { logger } from "../../../shell/logger.ts";
import { Cite } from "./Cite.tsx";

interface ArticleViewProps {
  repository: CatalogRepository;
  slug: string;
  onNews: () => void;
  onProduct: (slug: string) => void;
  onVendor: (slug: string) => void;
}

export const ArticleView: FC<ArticleViewProps> = ({ repository, slug, onNews, onProduct, onVendor }) => {
  const { t, locale } = useI18n();
  const article = useRead(() => repository.article(slug), `article:${slug}`,
    (err) => logger.error("news: an article failed to load", { page: "article", slug }, err));
  const view = article.value;
  const head = useMemo(() => (view ? buildArticleHeadMeta(view, SITE_ORIGIN, locale) : null), [view, locale]);
  useRecordHead(head, !article.isLoading && !article.error, t("articleNotFound"));

  const trail =
    <Breadcrumbs label={t("breadcrumbLabel")} trail={[{ label: t("newsTitle"), href: NEWS_PATH, onOpen: onNews }]} />;
  if (!view) return <DetailState loading={article.isLoading} failed={article.error} trail={trail}
    missing={t("articleNotFound")} skeleton={{ count: 3, type: "row" }} />;
  const facts = [{ key: "added", label: t("newsAdded"),
    value: <time dateTime={view.published_at}>{formatDate(view.published_at, locale)}</time> }];
  if (view.event_date && view.event_source) {
    facts.push({ key: "release", label: t("newsVendorRelease"),
      value: <>{formatPartialDate(view.event_date, locale)} <SourceChip source={view.event_source}
        locale={locale} /></> });
  }
  return (
    <article className="space-y-4 max-w-3xl">
      <div className="space-y-1">
        {trail}
        <PageHeader title={localized(view.title, locale)} lead={localized(view.summary, locale)}>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted">
            <Badge>{localized(view.kind.label, locale)}</Badge>
            <span>{t("newsBy", { byline: localized(view.byline, locale) })}</span>
            {view.authorship === "ai_draft"
              && <span>{t("newsAiDrafted", { date: formatDate(view.published_at, locale) })}</span>}
          </p>
          <Facts layout="grid" className="text-caption" facts={facts} />
        </PageHeader>
      </div>
      <div className="space-y-2">
        {view.body.map((sentence, n) => (
          <p key={n} className="text-body leading-relaxed">
            {localized(sentence.text, locale)}{" "}
            <span className="text-caption text-muted">
              ({t("newsCites")}{" "}
              {sentence.cites.map((cite, i) => (
                <span key={cite.id}>{i > 0 && ", "}<Cite cite={cite} onProduct={onProduct} onVendor={onVendor} /></span>
              ))})
            </span>
          </p>
        ))}
      </div>
    </article>
  );
};
