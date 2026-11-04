import { Fragment, type FC } from "react";
import type { ComponentLink, ProductLink, ProductView, RelationRow } from "../../../domain/views.ts";
import { historyPath, hubPath, productPath } from "../../../domain/paths.ts";
import { AppLink, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

export interface ProductLinksProps {
  product: ProductView;
  onSelectProduct: (productSlug: string) => void;
  onOpenHistory: (productSlug: string) => void;
  onOpenHub: (path: string, slug: string) => void;
}

type Linked = Pick<ProductLink, "id"
  | "name"> & { readonly href: string; readonly open: () => void; readonly note?: string };

const LINK = "font-medium text-fg-secondary underline hover:text-fg";

function grouped(rows: readonly RelationRow[], locale: string): [string, RelationRow[]][] {
  const groups = new Map<string, RelationRow[]>();
  for (const row of rows) {
    const label = localized(row.label, locale);
    groups.set(label, [...(groups.get(label) ?? []), row]);
  }
  return [...groups];
}

export const ProductLinks: FC<ProductLinksProps> = ({ product, onSelectProduct, onOpenHistory, onOpenHub }) => {
  const { t, plural, locale } = useI18n();
  const toProduct = (it: ProductLink, note?: string): Linked =>
    ({ id: it.id, name: it.name, href: productPath(it.slug), open: () => onSelectProduct(it.slug), note });
  const toHub = (c: ComponentLink): Linked =>
    ({ id: c.id, name: c.name, href: hubPath(c.hub, c.slug), open: () => onOpenHub(c.hub, c.slug) });
  const links = (label: string, items: readonly Linked[], kind: string) =>
    items.length > 0 && (
      <span key={label} data-links={kind} className="inline-flex flex-wrap items-center gap-x-1.5">
        <span className="text-muted">{label}</span>
        {items.map((it) => (
          <Fragment key={it.id}>
            <AppLink href={it.href} onOpen={it.open} className={LINK}>{it.name}</AppLink>
            {it.note && <span className="text-muted">({it.note})</span>}
          </Fragment>
        ))}
      </span>
    );
  const usedBy = product.hub;
  return (
    <>
      {product.family && links(t("familyLink"), [toProduct(product.family)], "family")}
      {grouped(product.relations, locale).map(([label, rows]) =>
        links(label, rows.map((r) => toProduct(r.product, r.basis === "derived" ? t("relationDerived") : undefined)),
          "relation"))}
      {links(t("usesTitle"), product.components.map(toHub), "components")}
      {usedBy && (
        <span data-links="hub">
          <AppLink href={hubPath(usedBy.path, product.slug)} onOpen={() => onOpenHub(usedBy.path, product.slug)}
            className={LINK}>{plural("usedByOne", "usedByOther", usedBy.users)}</AppLink>
        </span>
      )}
      {product.history && <AppLink href={historyPath(product.slug)} onOpen={() => onOpenHistory(product.slug)}
        className={LINK}>{t("historyLink")}</AppLink>}
    </>
  );
};
