import { type FC } from "react";
import { BrandLinks, PageHeader, Section } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { ROLE_LABELS } from "../../shell/i18n/roles.ts";
import { BRAND_CONFIG } from "../../ui/theme/brand.ts";
import { LEGAL_PAGES } from "./copy.ts";

export const LegalView: FC<{ page: keyof typeof LEGAL_PAGES }> = ({ page }) => {
  const { t } = useI18n();
  const { title, lead, sections, role } = LEGAL_PAGES[page];
  const params = { brand: BRAND_CONFIG.wordmark, licence: BRAND_CONFIG.licence.name, report: t("reportErrorAction") };
  const addresses = BRAND_CONFIG.contact.filter((c) => c.role === role)
    .map((c) => ({ label: t(ROLE_LABELS[c.role]), address: c.address }));
  return (
    <div className="max-w-3xl space-y-4">
      <PageHeader title={t(title)} lead={t(lead)} />
      {sections.map(({ heading, text, link }) => (
        <Section key={text} title={t(heading)}>
          <p className="text-body text-fg-secondary leading-relaxed">{t(text, params)}</p>
          {link && <a href={link.href} rel="license noopener noreferrer" target="_blank"
            className="text-body underline text-fg-secondary hover:text-fg">{t(link.label, params)}</a>}
        </Section>
      ))}
      <BrandLinks label={t("contactLabel")} profiles={[]} addresses={addresses} className="text-body text-muted" />
    </div>
  );
};
