import { type FC } from "react";
import { BrandLinks, Facts, PageHeader, Section, useRegistry } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { ROLE_LABELS } from "../../shell/i18n/roles.ts";
import { BRAND_CONFIG } from "../../ui/theme/brand.ts";
import { PRINCIPLES, domainList } from "./copy.ts";

export const AboutView: FC = () => {
  const { t, locale } = useI18n();
  const { domains } = useRegistry();
  return (
    <div className="max-w-3xl space-y-4">
      <PageHeader title={t("aboutTitle", { brand: BRAND_CONFIG.wordmark })} lead={
        <>
          <p>{t("aboutDescription", { count: domains.length, domains: domainList(domains, locale) })}</p>
          <p className="mt-1">{t("provenanceNote")}</p>
        </>
      } />
      <Section title={t("dataPrinciplesTitle")}>
        <Facts layout="grid" className="text-body"
          facts={PRINCIPLES.map(([term, description]) => ({ key: term, label: t(term), value: t(description) }))} />
      </Section>
      <BrandLinks label={t("contactLabel")} profiles={BRAND_CONFIG.profiles} className="text-body text-muted"
        addresses={BRAND_CONFIG.contact.map((c) => ({ label: t(ROLE_LABELS[c.role]), address: c.address }))} />
    </div>
  );
};
