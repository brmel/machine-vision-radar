import type { FC } from "react";
import type { IndexCounts } from "../../src/domain/views.ts";
import { TYPE } from "../../src/ui/index.ts";
import { DEFAULT_MESSAGES as messages, fill } from "../../src/shell/i18n/messages.ts";
import { Frame, type Stamp } from "./Frame.tsx";

export type CatalogCardProps = Stamp & { counts: IndexCounts };

export const CATALOG_NONE: CatalogCardProps = { address: "", asOf: null,
  counts: { products: 0, organizations: 0, categories: 0 } };

export const CatalogCard: FC<CatalogCardProps> = ({ counts, ...stamp }) => (
  <Frame {...stamp}>
    <div className="h-full flex flex-col justify-center gap-4">
      <p className={TYPE.display}>{fill(messages.liveStats,
        { products: counts.products, vendors: counts.organizations, categories: counts.categories })}</p>
      <p className="text-lead text-fg-secondary">{messages.footerNote}</p>
    </div>
  </Frame>
);
