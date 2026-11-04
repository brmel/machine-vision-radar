import type { FC } from "react";
import type { OrganizationView } from "../../domain/views.ts";
import { vendorPath } from "../../domain/paths.ts";
import { AppLink, SourceChip, Section, formatPartialDate, localized } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";

type Relation = OrganizationView["ownership"][number];

export const OwnershipList: FC<{ vendor: OrganizationView; onSelectVendor: (vendorSlug: string) => void }> = ({ vendor,
  onSelectVendor }) => {
  const { t, locale } = useI18n();
  const org = (o: Relation["from_org"]) =>
    o.slug === vendor.slug ? <span className="font-medium">{o.name}</span> : (
      <AppLink href={vendorPath(o.slug)} onOpen={() => onSelectVendor(o.slug)}
        className="font-medium underline">{o.name}</AppLink>
    );
  const item = (r: Relation) => {
    const source = r.source ? vendor.sources.find((s) => s.id === r.source) : undefined;
    return (
      <li key={`${r.from_org.id}-${r.type.id}-${r.to_org.id}`}
        className="flex flex-wrap items-center gap-x-2 gap-y-1 text-body text-fg-secondary">
        {r.valid_from
          && <span className="font-mono text-caption tabular-nums">{formatPartialDate(r.valid_from, locale)}</span>}
        {org(r.from_org)}
        <span className="text-muted">{localized(r.type.label, locale)}</span>
        {org(r.to_org)}
        {source && <SourceChip source={source} locale={locale} />}
      </li>
    );
  };
  return (
    <Section title={t("ownershipTitle")}>
      <ul className="space-y-1">{vendor.ownership.map(item)}</ul>
    </Section>
  );
};
