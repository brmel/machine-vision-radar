import { type FC, useEffect, useState } from "react";
import type { FacetView } from "../../../domain/views.ts";
import { boundOf, type Range } from "../../../domain/filtering/filterUrl.ts";
import { facetLabel, localized, prevented } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

interface RangeFacetProps {
  facet: FacetView;
  range: Range | undefined;
  onRange: (range: Range) => void;
}

const format = (value: number | undefined, locale: string): string => (value === undefined ? ""
  : new Intl.NumberFormat(locale, { maximumFractionDigits: 6, useGrouping: false }).format(value));

const parse = (text: string): number | undefined | null => (text.trim() === "" ? undefined : boundOf(text));

export const RangeFacet: FC<RangeFacetProps> = ({ facet, range, onRange }) => {
  const { t, locale } = useI18n();
  const title = facetLabel(facet, locale);
  const [min, setMin] = useState(format(range?.min, locale));
  const [max, setMax] = useState(format(range?.max, locale));
  useEffect(() => setMin(format(range?.min, locale)), [range?.min, locale]);
  useEffect(() => setMax(format(range?.max, locale)), [range?.max, locale]);
  const typed = { min, max };

  const commit = () => {
    const [low, high] = [parse(min), parse(max)];
    const next = { min: low === null ? range?.min : low, max: high === null ? range?.max : high };
    if (next.min !== range?.min || next.max !== range?.max) onRange(next);
  };
  const submit = prevented(commit);
  const box = (bound: keyof Range, label: string, hint: number | undefined) => (
    <label className="flex-1 min-w-0 space-y-0.5">
      <span className="block text-caption text-muted">{label}</span>
      <input
        type="text"
        inputMode="decimal"
        value={typed[bound]}
        placeholder={format(hint, locale)}
        aria-label={`${title}, ${label}`}
        onChange={(e) => (bound === "min" ? setMin : setMax)(e.target.value)}
        onBlur={commit}
        className={"w-full rounded-control border border-line-strong bg-surface px-2 py-1 text-caption font-mono "
          + "tabular-nums text-fg placeholder:text-muted focus:outline-none focus-visible:border-focus"}
      />
    </label>
  );

  return (
    <form onSubmit={submit} className="space-y-2" role="group" aria-label={title}>
      <h3 className="text-caption font-heading text-fg-secondary"
        title={facet.description && localized(facet.description, locale)}>{title}</h3>
      <div className="flex items-end gap-2">
        {box("min", t("rangeFrom"), facet.min)}
        {box("max", t("rangeTo"), facet.max)}
        {facet.unit && <span className="pb-1.5 text-caption text-muted">{facet.unit}</span>}
        <button type="submit" hidden />
      </div>
    </form>
  );
};
