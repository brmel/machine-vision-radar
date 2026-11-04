import type { FC } from "react";
import type { OrganizationView } from "../../domain/views.ts";
import { PageHeader, WebsiteLink, formatCountry, localized, localizedLang } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";

export const VendorHeader: FC<{ vendor: OrganizationView; total: number }> = ({ vendor, total }) => {
  const { t, plural, locale } = useI18n();
  const website = vendor.website?.trim() ? vendor.website : undefined;
  return (
    <PageHeader
      title={vendor.name}
      count={total > 0 && plural("productCountOne", "productCountOther", total)}
      lead={vendor.summary && <p lang={localizedLang(vendor.summary, locale)}>{localized(vendor.summary, locale)}</p>}
      actions={website && <WebsiteLink href={website} label={t("officialWebsite")} />}
    >
      <p className="text-caption text-muted">{vendor.country ? formatCountry(vendor.country, locale)
        : t("unknownValue")}</p>
    </PageHeader>
  );
};
