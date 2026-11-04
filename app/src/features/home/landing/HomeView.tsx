import { type FC } from "react";
import type { RegistryView } from "../../../domain/views.ts";
import { NEWS_PATH } from "../../../domain/paths.ts";
import { AppLink, Section } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { NewsList } from "../news/NewsList.tsx";
import { HomeHero } from "./HomeHero.tsx";
import { PipelineSection } from "./PipelineSection.tsx";

interface HomeViewProps {
  registry: Pick<RegistryView, "counts" | "data_as_of" | "news">;
  query: string;
  onQueryChange: (query: string) => void;
  onSearch: (query: string) => void;
  onBrowse: (filters?: { domain?: string; stage?: string }) => void;
  onNews: () => void;
  onMarket: () => void;
  onArticle: (slug: string) => void;
}

export const HomeView: FC<HomeViewProps> = ({ registry, query, onQueryChange, onSearch, onBrowse, onNews,
  onMarket, onArticle }) => {
  const { t } = useI18n();
  const { counts, data_as_of: dataAsOf, news } = registry;

  return (
    <div className="space-y-8">
      <HomeHero counts={counts} dataAsOf={dataAsOf} query={query} onQueryChange={onQueryChange} onSearch={onSearch}
        onMarket={onMarket} />

      <PipelineSection onBrowse={onBrowse} />

      {news.length > 0 && (
        <Section id="latest-news" title={t("newsLatest")} aside={<AppLink href={NEWS_PATH} onOpen={onNews}
          className="text-caption underline text-fg-secondary">{t("newsBack")}</AppLink>}>
          <NewsList items={news} onOpen={onArticle} level={3} />
        </Section>
      )}
    </div>
  );
};
