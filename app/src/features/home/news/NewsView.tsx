import { useMemo, type FC } from "react";
import type { CatalogRepository } from "../../../domain/ports/CatalogRepository.ts";
import { PAGE_SIZE } from "../../../domain/ports/CatalogRepository.ts";
import type { FeedBrief } from "../../../domain/views.ts";
import { NEWS_PATH, pageCount, pageOf } from "../../../domain/paths.ts";
import { Chip, PageHeader, Pagination, StatePanel, localized, useRead } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { usePagerLabels } from "../../../shell/i18n/labels.ts";
import { ReadState } from "../../../shell/layout/ReadState.tsx";
import { buildNewsHeadMeta } from "../../../shell/seo/news.ts";
import { useRecordHead } from "../../../shell/seo/documentHead.ts";
import { SITE_ORIGIN } from "../../../shell/seo/siteOrigin.ts";
import { logger } from "../../../shell/logger.ts";
import { NewsList } from "./NewsList.tsx";

interface NewsViewProps {
  repository: CatalogRepository;
  query: string;
  onQuery: (query: string) => void;
  onOpen: (slug: string) => void;
}

const written = (kind: string, page: number): string =>
  new URLSearchParams([...(kind ? [["kind", kind]] : []), ...(page > 1 ? [["page", String(page)]] : [])]).toString();

function kindsOf(items: readonly FeedBrief[]): { kind: FeedBrief["kind"]; count: number }[] {
  const kinds = new Map<string, { kind: FeedBrief["kind"]; count: number }>();
  for (const item of items)
    kinds.set(item.kind.id, { kind: item.kind, count: (kinds.get(item.kind.id)?.count ?? 0) + 1 });
  return [...kinds.values()];
}

export const NewsView: FC<NewsViewProps> = ({ repository, query, onQuery, onOpen }) => {
  const { t, plural, locale } = useI18n();
  const pager = usePagerLabels();
  const news = useRead(() => repository.news(), "news",
    (err) => logger.error("news: the articles failed to load", { page: "news" }, err));
  const head = useMemo(() => (news.value
    ? buildNewsHeadMeta(news.value.items.slice(0, PAGE_SIZE), news.value.total, SITE_ORIGIN) : null), [news.value]);
  useRecordHead(head);

  const feeds = (
    <>
      <a href={`${NEWS_PATH}/feed.atom`} type="application/atom+xml"
        className="text-caption underline text-fg-secondary">{t("newsAtom")}</a>
      <a href={`${NEWS_PATH}/feed.json`} type="application/feed+json"
        className="text-caption underline text-fg-secondary">{t("newsJsonFeed")}</a>
    </>
  );
  const heading = (count?: number) => (
    <PageHeader title={t("newsTitle")} lead={t("newsDescription")} actions={feeds}
      count={count !== undefined && <span role="status">{plural("newsCountOne", "newsCountOther", count)}</span>} />
  );
  if (!news.value) {
    return (
      <div className="space-y-3">
        {heading()}
        <ReadState failed={news.error} skeleton={{ count: 4, type: "row" }} />
      </div>
    );
  }

  const kind = new URLSearchParams(query).get("kind") ?? "";
  const kinds = kindsOf(news.value.items);
  const shown = news.value.items.filter((item) => !kind || item.kind.id === kind);
  const pages = pageCount(shown.length, PAGE_SIZE);
  const current = Math.min(pageOf(query), pages);
  return (
    <div className="space-y-3">
      {heading(shown.length)}
      {kinds.length > 1 && (
        <div role="group" aria-label={t("newsFilterLabel")} className="flex flex-wrap gap-2">
          <Chip label={t("newsAllKinds")} active={!kind} aria-pressed={!kind} onClick={() => onQuery(written("", 1))} />
          {kinds.map((k) => (
            <Chip key={k.kind.id} label={localized(k.kind.label, locale)} count={k.count} active={kind === k.kind.id}
              aria-pressed={kind === k.kind.id} onClick={() => onQuery(written(k.kind.id, 1))} />
          ))}
        </div>
      )}
      {shown.length > 0
        ? <NewsList items={shown.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)} onOpen={onOpen} level={2} />
        : <StatePanel tone="empty" title={t(kind ? "newsNoneOfKind" : "newsEmpty")} />}
      <Pagination page={current} pageSize={PAGE_SIZE} totalCount={shown.length}
        onPageChange={(p) => onQuery(written(kind, p))} {...pager} />
    </div>
  );
};
