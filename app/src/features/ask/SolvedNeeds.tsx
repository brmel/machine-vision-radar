import { type FC } from "react";
import type { AskNeed, ProductView } from "../../domain/views.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { CitedProducts } from "./CitedProducts.tsx";

interface SolvedNeedsProps {
  needs: readonly AskNeed[];
  cited: ReadonlyMap<string, ProductView>;
  onSelectProduct: (slug: string) => void;
}

export const SolvedNeeds: FC<SolvedNeedsProps> = ({ needs, cited, onSelectProduct }) => {
  const { t } = useI18n();
  return (
    <ol className="space-y-4">
      {needs.map((need) => (
        <li key={need.need} className="space-y-1.5">
          <h3 className="font-heading text-fg">{need.need}</h3>
          {need.answer ? (
            <>
              <p className="ask-answer text-fg leading-relaxed">{need.answer}</p>
              <CitedProducts citations={need.citations} cited={cited} onSelectProduct={onSelectProduct}
                label={t("askCited")} />
            </>
          ) : <p className="text-muted">{t("askNeedUnmet")}</p>}
        </li>
      ))}
    </ol>
  );
};
