import { type FC, type ReactNode } from "react";
import type { OfferingRow, PartialDate, ProductView, SourceView, TermRef, VersionRow } from "../../../domain/views.ts";
import { Badge, CELL, Section, SourceChip, Table, formatPartialDate, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

type Field<R> = { key: keyof R & string; label: string; cell: (row: R) => ReactNode };

function Rows<R extends { id: string; source?: string }>({ caption, rows, fields, sources, locale, sourceLabel }: {
  caption: string; rows: readonly R[]; fields: readonly Field<R>[]; sources: Map<string, SourceView>; locale: string;
  sourceLabel: string;
}) {
  const shown = fields.filter((f) => rows.some((r) => r[f.key] !== undefined));
  return (
    <Section title={caption}>
      <Table columns={[...shown.map((f) => ({ head: f.label })), { head: sourceLabel }]} className="text-caption">
        {rows.map((r) => {
          const source = r.source ? sources.get(r.source) : undefined;
          return (
            <tr key={r.id}>
              {shown.map((f) => <td key={f.key} className={CELL}>{r[f.key] === undefined ? "" : f.cell(r)}</td>)}
              <td className={CELL}>{source && <SourceChip source={source} locale={locale} />}</td>
            </tr>
          );
        })}
      </Table>
    </Section>
  );
}

export const ProductLifecycle: FC<{ product: ProductView }> = ({ product }) => {
  const { t, locale } = useI18n();
  const sources = new Map(product.sources.map((s) => [s.id, s]));
  const date = (d: PartialDate | undefined) => (d ? formatPartialDate(d, locale) : "");
  const term = (x: TermRef | undefined) => (x ? localized(x.label, locale) : "");
  const versionFields: Field<VersionRow>[] = [
    { key: "label", label: t("versionField_label"), cell: (r) => <span className="font-mono">{r.label}</span> },
    { key: "channel", label: t("versionField_channel"), cell: (r) => term(r.channel) },
    { key: "released", label: t("versionField_released"), cell: (r) => date(r.released) },
    { key: "end_of_support", label: t("versionField_end_of_support"), cell: (r) => date(r.end_of_support) },
  ];
  const offeringFields: Field<OfferingRow>[] = [
    { key: "licence_type", label: t("offeringField_licence_type"), cell: (r) => term(r.licence_type) },
    { key: "term", label: t("offeringField_term"), cell: (r) => term(r.term) },
    { key: "binding", label: t("offeringField_binding"), cell: (r) => term(r.binding) },
    { key: "price", label: t("offeringField_price"),
      cell: (r) => (r.price ? `${r.price.amount} ${r.price.currency}` : "") },
    { key: "valid_from", label: t("offeringField_valid_from"), cell: (r) => date(r.valid_from) },
    { key: "valid_to", label: t("offeringField_valid_to"), cell: (r) => date(r.valid_to) },
  ];
  return (
    <div className="space-y-4 empty:hidden">
      {product.versions.length > 0 && (
        <Rows caption={t("versionsTitle")} rows={product.versions} fields={versionFields} sources={sources}
          locale={locale} sourceLabel={t("tabSources")} />
      )}
      {product.offerings.length > 0 && (
        <Rows caption={t("offeringsTitle")} rows={product.offerings} fields={offeringFields} sources={sources}
          locale={locale} sourceLabel={t("tabSources")} />
      )}
      {product.lifecycle.length > 0 && (
        <Section title={t("lifecycleTitle")}>
          <ol className="lifecycle space-y-1 border-l border-line pl-3">
            {product.lifecycle.map((e) => {
              const source = e.source ? sources.get(e.source) : undefined;
              return (
                <li key={e.id} data-state={e.state.id}
                  className="flex flex-wrap items-center gap-2 text-caption text-fg-secondary">
                  <span className="tabular-nums font-mono">{date(e.date)}</span>
                  <span className="font-medium">{term(e.type)}</span>
                  {!e.occurred && (
                    <Badge tone="warning" className="lifecycle-state">{term(e.state)}</Badge>
                  )}
                  {source && <SourceChip source={source} locale={locale} />}
                </li>
              );
            })}
          </ol>
        </Section>
      )}
    </div>
  );
};
