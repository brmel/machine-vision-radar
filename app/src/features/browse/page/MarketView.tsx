import { type FC } from "react";
import type { CatalogRepository } from "../../../domain/ports/CatalogRepository.ts";
import type { OrgBrief } from "../../../domain/views.ts";
import { categoryPath, vendorPath } from "../../../domain/paths.ts";
import { AppLink, PageHeader, ReadState, Section, formatCountry, localized, useRead,
  useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useReadStateLabels } from "../../../shell/i18n/labels.ts";
import { logger } from "../../../shell/logger.ts";
import { Counts } from "./Counts.tsx";

interface MarketViewProps {
  repository: CatalogRepository;
  onCategory: (category: string) => void;
  onVendor: (vendor: string) => void;
}

export const MarketView: FC<MarketViewProps> = ({ repository, onCategory, onVendor }) => {
  const { t, locale } = useI18n();
  const { categories } = useRegistry();
  const states = useReadStateLabels();
  const market = useRead(() => repository.market(), "market",
    (err) => logger.error("market: the counts failed to load", { page: "market" }, err));
  const heading = <PageHeader title={t("marketTitle")} lead={t("marketDescription")} />;
  if (!market.value) {
    return (
      <div className="space-y-3">
        {heading}
        <ReadState failed={market.error} labels={states} skeleton={{ count: 4, type: "row" }} />
      </div>
    );
  }
  const counts = market.value;
  const country = (code?: string) => (code ? formatCountry(code, locale) : "—");
  const category = (id: string) => {
    const entry = categories.find((e) => e.id === id);
    return <AppLink href={categoryPath(id)} onOpen={() => onCategory(id)} className="underline">
      {entry ? localized(entry.label, locale) : id}</AppLink>;
  };
  const vendor = (org: OrgBrief) =>
    <AppLink href={vendorPath(org.slug)} onOpen={() => onVendor(org.slug)} className="underline">{org.name}</AppLink>;
  const tables = [
    { title: t("marketCategoriesTitle"),
      note: t("marketCategoriesBase", { products: counts.categories.reduce((sum, c) => sum + c.products, 0) }),
      heads: [t("marketCategory"), t("marketProducts"), t("marketVendors")], numbers: [1, 2],
      rows: counts.categories.map((c) => ({ key: c.category, cells: [category(c.category), c.products, c.vendors] })) },
    { title: t("marketVendorsTitle"),
      note: t("marketVendorsBase", { vendors: counts.vendors.length, organizations: counts.organizations }),
      heads: [t("marketVendor"), t("marketCountry"), t("marketProducts"), t("marketCategories")], numbers: [2, 3],
      rows: counts.vendors.map((v) => ({ key: v.organization.slug,
        cells: [vendor(v.organization), country(v.organization.country), v.products, v.categories] })) },
    { title: t("marketCountriesTitle"),
      note: t("marketCountriesBase", { located: counts.countries.reduce((sum, c) => sum + c.organizations, 0),
        organizations: counts.organizations }),
      heads: [t("marketCountry"), t("marketOrganizations"), t("marketProducts")], numbers: [1, 2],
      rows: counts.countries.map((c) =>
        ({ key: c.country, cells: [country(c.country), c.organizations, c.products] })) },
    { title: t("marketOwnershipTitle"), note: t("marketOwnershipBase"),
      heads: [t("marketYear"), t("marketCompany"), t("marketType"), t("marketOwner")], numbers: [],
      rows: counts.consolidation.map((e) => ({ key: `${e.year}-${e.organization.slug}-${e.type.id}-${e.owner.slug}`,
        cells: [e.year ?? "—", vendor(e.organization), localized(e.type.label, locale), vendor(e.owner)] })) },
  ];
  return (
    <div className="space-y-5">
      {heading}
      <div className="grid grid-cols-1 gap-x-8 gap-y-6 lg:grid-cols-2 items-start">
        {tables.map((table) => (
          <Section key={table.title} title={table.title} note={table.note}>
            <Counts label={table.title} heads={table.heads} numbers={table.numbers} rows={table.rows} />
          </Section>
        ))}
      </div>
    </div>
  );
};
