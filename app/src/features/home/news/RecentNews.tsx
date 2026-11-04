import type { FC } from "react";
import type { CatalogRepository } from "../../../domain/ports/CatalogRepository.ts";
import { Section, useRead } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { logger } from "../../../shell/logger.ts";
import { NewsList } from "./NewsList.tsx";

const RECENT = 3;

interface RecentNewsProps {
  repository: CatalogRepository;
  about: string;
  onOpen: (slug: string) => void;
}

export const RecentNews: FC<RecentNewsProps> = ({ repository, about, onOpen }) => {
  const { t } = useI18n();
  const news = useRead(() => repository.news(), "news",
    (err) => logger.warn("news: the recent articles were not read", { page: "recent-news" }, err));
  const items = (news.value?.items ?? [])
    .filter((item) => item.subjects.includes(about) || item.categories.includes(about)).slice(0, RECENT);
  if (items.length === 0) return null;
  return (
    <Section id="recent-news" title={t("newsRecent")}>
      <NewsList items={items} onOpen={onOpen} level={3} />
    </Section>
  );
};
