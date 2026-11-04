import type { FC } from "react";
import type { FeedBrief } from "../../../domain/views.ts";
import { articlePath } from "../../../domain/paths.ts";
import { AppLink, Badge, TYPE, formatDate, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

interface NewsListProps {
  items: readonly FeedBrief[];
  onOpen: (slug: string) => void;
  level: 2 | 3;
}

export const NewsList: FC<NewsListProps> = ({ items, onOpen, level }) => {
  const { locale } = useI18n();
  const Title = level === 2 ? "h2" : "h3";
  return (
    <ol className="divide-y divide-line">
      {items.map((item) => (
        <li key={item.slug} className="py-2 space-y-0.5">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <Title className={TYPE.label}>
              <AppLink href={articlePath(item.slug)} onOpen={() => onOpen(item.slug)}
                className="hover:underline">{localized(item.title, locale)}</AppLink>
            </Title>
            <span className="inline-flex items-center gap-2 text-caption text-muted">
              <Badge>{localized(item.kind.label, locale)}</Badge>
              <time dateTime={item.published_at}>{formatDate(item.published_at, locale)}</time>
            </span>
          </div>
          <p className="text-caption text-fg-secondary">{localized(item.summary, locale)}</p>
        </li>
      ))}
    </ol>
  );
};
