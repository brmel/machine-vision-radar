import type { ChangeEvent, FC } from "react";
import type { RegistryView } from "../../../domain/views.ts";
import { AppLink, SearchInput, TYPE, prevented } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { BRAND_CONFIG } from "../../../ui/theme/brand.ts";
import { formatDate } from "../../../ui/specs/specFormat.ts";

interface HomeHeroProps {
  counts: RegistryView["counts"];
  dataAsOf: RegistryView["data_as_of"];
  query: string;
  onQueryChange: (query: string) => void;
  onSearch: (query: string) => void;
  onMarket: () => void;
}

export const HomeHero: FC<HomeHeroProps> = ({ counts, dataAsOf, query, onQueryChange, onSearch, onMarket }) => {
  const { t, locale } = useI18n();
  const updateQuery = (event: ChangeEvent<HTMLInputElement>) => onQueryChange(event.target.value);
  const clear = () => onQueryChange("");
  return (
    <div className="text-center max-w-5xl mx-auto space-y-4 pt-2 sm:pt-4">
      <div className="space-y-2">
        <h1 className={TYPE.display}>{BRAND_CONFIG.wordmark}</h1>
        <p className="text-body sm:text-lead text-fg-secondary leading-relaxed">{t("heroSubtitle")}</p>
      </div>
      <form onSubmit={prevented(() => onSearch(query))} className="max-w-2xl mx-auto text-left">
        <SearchInput value={query} onChange={updateQuery} onClear={clear} placeholder={t("searchInputPlaceholder")}
          clearLabel={t("ariaClearInput")} />
      </form>
      <p className={"flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-caption sm:text-body font-mono "
        + "text-muted"}>
        <span>{t("liveStats",
          { products: counts.products, vendors: counts.organizations, categories: counts.categories })}</span>
        <span aria-hidden="true" className="text-faint">·</span>
        <span>{t("dataUpdatedLabel", { date: dataAsOf ? formatDate(dataAsOf, locale) : t("unknownValue") })}</span>
        <span aria-hidden="true" className="text-faint">·</span>
        <AppLink href="/market" onOpen={onMarket}
          className="underline text-fg-secondary">{t("homeMarketLink")}</AppLink>
      </p>
    </div>
  );
};
