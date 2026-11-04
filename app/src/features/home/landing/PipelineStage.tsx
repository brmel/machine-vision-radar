import type { FC } from "react";
import { ChevronRight } from "lucide-react";
import { AppLink, Badge, TYPE } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { localized } from "../../../ui/specs/specFormat.ts";
import type { TermCount } from "../copy.ts";
import { browsePath } from "../../../domain/paths.ts";
import { browseQuery } from "../../../domain/filtering/filterUrl.ts";

interface PipelineStageProps {
  stage: TermCount;
  index: number;
  count: number;
  onBrowse: (filters: { stage: string }) => void;
}

export const PipelineStage: FC<PipelineStageProps> = ({ stage: { term, products }, index, count, onBrowse }) => {
  const { plural, locale } = useI18n();
  return (
    <li className="relative motion-safe:animate-rise" style={{ animationDelay: `${index * 50}ms` }}>
      <AppLink href={browsePath(browseQuery({ stage: term.id }))} onOpen={() => onBrowse({ stage: term.id })}
        className={"flex h-full flex-col gap-2 p-4 rounded-card border border-line bg-surface "
          + "transition-[border-color,box-shadow] duration-150 hover:border-line-hover hover:shadow-field"}>
        <span className="flex items-center gap-2">
          <Badge tone="accent" className="font-mono">{String(index + 1).padStart(2, "0")}</Badge>
          <span className={TYPE.label}>{localized(term.label, locale)}</span>
        </span>
        <span className="text-caption text-fg-secondary">{localized(term.description, locale)}</span>
        <span className="mt-auto font-mono text-caption text-muted tabular-nums">{plural("productCountOne",
          "productCountOther", products)}</span>
      </AppLink>
      {index < count - 1 && (
        <ChevronRight aria-hidden="true" style={{ animationDelay: `${count * 50 + 200}ms` }}
          className={`absolute size-5 left-full top-1/2 -translate-y-1/2 text-faint motion-safe:animate-nudge `
            + `${index % 2 === 1 ? "max-sm:hidden" : ""} ${index % 3 === 2 ? "sm:max-lg:hidden" : ""}`} />
      )}
    </li>
  );
};
