import { type FC, useState } from "react";
import type { ProductView } from "../../../domain/views.ts";
import { Section, Segmented, SpecTable, localized, localizedLang, specRowLabel,
  useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useValueLabels } from "../../../shell/i18n/labels.ts";
import { FamilyModels } from "./FamilyModels.tsx";
import { SourcesList } from "./SourcesList.tsx";
import { ProductLifecycle } from "./ProductLifecycle.tsx";
import { ProductMedia } from "./ProductMedia.tsx";

interface ProductTabsProps {
  product: ProductView;
  onSelectProduct: (slug: string) => void;
}

type Cells = ProductView["core"];

function byGroup(cells: Cells): { group?: string; cells: Cells }[] {
  return cells.reduce<{ group?: string; cells: Cells }[]>((runs, cell) => {
    const last = runs[runs.length - 1];
    return last && last.group === cell.group ? [...runs.slice(0, -1), { ...last, cells: [...last.cells, cell] }]
      : [...runs, { group: cell.group, cells: [cell] }];
  }, []);
}

export const ProductTabs: FC<ProductTabsProps> = ({ product, onSelectProduct }) => {
  const [activeTab, setActiveTab] = useState<"specs" | "sources">("specs");
  const { t, locale, plural } = useI18n();
  const { spec_definitions: specDefs, spec_groups: groups } = useRegistry();
  const labels = useValueLabels();
  const core = product.core.filter((c) => c.value !== undefined);
  const detail = byGroup(product.detail.filter((c) => c.value !== undefined));
  const runs = [...(core.length > 0 ? [{ title: t("specSectionCore"), cells: core }] : []),
    ...detail.flatMap((run) => (run.group ? [{ title: localized(groups[run.group], locale), cells: run.cells }]
      : [])),
    ...detail.flatMap((run) => (run.group ? [] : [{ title: t("specGroupOther"), cells: run.cells }]))];
  const cells = [...product.core, ...product.detail];
  const unpublished = cells.filter((c) => c.value === undefined);
  return (
    <>
      <Segmented look="tab" label={t("productTabsLabel")} value={activeTab} onChange={setActiveTab} options={[
        { id: "specs", label: t("tabSpecs"), count: cells.length - unpublished.length },
        { id: "sources", label: t("tabSources"), count: product.sources.length },
      ]} />

      {activeTab === "specs" && (
        <div className="space-y-4">
          {runs.length > 0
            && <SpecTable runs={runs} sources={product.sources} specDefs={specDefs} labels={labels} />}
          {unpublished.length > 0 && (
            <details className="spec-unpublished">
              <summary className="cursor-pointer text-body text-muted">{plural("specsNotPublishedOne",
                "specsNotPublishedOther", unpublished.length)}</summary>
              <ul className={"pt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-0.5 text-caption "
                + "text-muted"}>
                {unpublished.map((c) => <li key={c.key}>{specRowLabel(c.key, specDefs, locale)}</li>)}
              </ul>
            </details>
          )}
          {product.summary && (
            <Section title={t("productDescription")}>
              <p lang={localizedLang(product.summary, locale)} className="max-w-3xl text-body text-fg-secondary">
                {localized(product.summary, locale)}</p>
            </Section>
          )}
          {product.models.length > 0 && <FamilyModels product={product} onSelectProduct={onSelectProduct} />}
          <ProductLifecycle product={product} />
          <ProductMedia media={product.media} />
        </div>
      )}
      {activeTab === "sources" && <SourcesList sources={product.sources} />}
    </>
  );
};
