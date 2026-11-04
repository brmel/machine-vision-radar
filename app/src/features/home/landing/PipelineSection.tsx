import type { FC } from "react";
import { AppLink, Section, useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { localized } from "../../../ui/specs/specFormat.ts";
import { pipeline } from "../copy.ts";
import { browsePath } from "../../../domain/paths.ts";
import { browseQuery } from "../../../domain/filtering/filterUrl.ts";
import { PipelineStage } from "./PipelineStage.tsx";

interface PipelineSectionProps {
  onBrowse: (filters: { domain?: string; stage?: string }) => void;
}

export const PipelineSection: FC<PipelineSectionProps> = ({ onBrowse }) => {
  const { t, plural, locale } = useI18n();
  const { categories, pipeline_stages: stages, domains } = useRegistry();
  const pipelineView = pipeline(stages, domains, categories);
  return (
    <>
      <Section id="pipeline" title={t("browseByPipelineTitle")}>
        <ol className="grid auto-rows-fr grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-3 lg:grid-cols-6">
          {pipelineView.stages.map((stage, index) => (
            <PipelineStage key={stage.term.id} stage={stage} index={index} count={pipelineView.stages.length}
              onBrowse={onBrowse} />
          ))}
        </ol>
      </Section>
      <Section id="domains" title={t("browseByDomainTitle")}>
        <nav aria-label={t("browseByDomainTitle")}>
          <ul className="grid auto-rows-fr grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {pipelineView.domains.map(({ term, products }) => (
              <li key={term.id}>
                <AppLink href={browsePath(browseQuery({ domain: term.id }))}
                  onOpen={() => onBrowse({ domain: term.id })}
                  className={"flex h-full flex-col gap-1 px-4 py-3 rounded-card border border-line bg-surface "
                    + "transition-[border-color,box-shadow] duration-150 hover:border-line-hover hover:shadow-field"}>
                  <span className="text-body font-heading text-fg">{localized(term.label, locale)}</span>
                  <span className="font-mono text-caption text-muted tabular-nums">{plural("productCountOne",
                    "productCountOther", products)}</span>
                </AppLink>
              </li>
            ))}
          </ul>
        </nav>
      </Section>
    </>
  );
};
