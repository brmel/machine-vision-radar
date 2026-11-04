import { type FC, useState } from "react";
import { Chip } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

export interface FacetOption {
  readonly id: string;
  readonly label: string;
  readonly count?: number;
  readonly on: boolean;
  readonly onClick: () => void;
  readonly title?: string;
  readonly section?: string;
}

const COLLAPSED = 8;

export const FacetGroup: FC<{ title: string; hint?: string; options: readonly FacetOption[];
  onReset: () => void }> = ({ title, hint, options, onReset }) => {
  const { t } = useI18n();
  const [words, setWords] = useState("");
  const [open, setOpen] = useState(true);
  const picked = options.some((o) => o.on);
  const long = options.length > COLLAPSED;
  const matching = options.filter((o) => o.label.toLowerCase().includes(words.trim().toLowerCase()));
  const shown = open || words ? matching : matching.filter((o, i) => i < COLLAPSED || o.on);
  const sections = [...new Set(shown.map((o) => o.section ?? ""))];
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-caption font-heading text-fg-secondary" title={hint}>{title}</h3>
        {picked && (
          <button type="button" onClick={onReset}
            className="text-micro text-muted underline cursor-pointer hover:text-fg">{t("facetReset")}</button>
        )}
      </div>
      {long && (
        <input type="search" value={words} onChange={(e) => setWords(e.target.value)}
          placeholder={t("facetFilterPlaceholder")}
          aria-label={t("facetFilterLabel", { facet: title })}
          className={"w-full px-2.5 py-1.5 text-caption bg-surface border border-line rounded-control text-fg "
            + "placeholder:text-faint"} />
      )}
      <div role="group" aria-label={title} className="space-y-2">
        {sections.map((section) => (
          <div key={section} className="space-y-1.5">
            {section && <p className="text-micro text-muted">{section}</p>}
            <div className="flex flex-wrap gap-1.5">
              {shown.filter((o) => (o.section ?? "") === section).map((o) => (
                <Chip key={o.id} label={o.label} count={o.count} active={o.on} aria-pressed={o.on} onClick={o.onClick}
                  title={o.title}
                  className={picked && !o.on ? "opacity-60 hover:opacity-100" : ""} />
              ))}
            </div>
          </div>
        ))}
      </div>
      {long && !words && (
        <button type="button" aria-expanded={open} onClick={() => setOpen((was) => !was)}
          className="text-micro text-muted underline cursor-pointer hover:text-fg">
          {open ? t("facetFewer") : t("moreCount", { count: options.length - shown.length })}
        </button>
      )}
    </div>
  );
};
