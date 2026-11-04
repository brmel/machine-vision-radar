import type { FC } from "react";
import type { SourceView, SpecCell } from "../../src/domain/views.ts";
import { SpecTable, TYPE } from "../../src/ui/index.ts";
import type { SpecDefinitions } from "../../src/ui/specs/specFormat.ts";
import { DEFAULT_MESSAGES, DEFAULT_VALUE_LABELS } from "../../src/shell/i18n/messages.ts";
import { Frame, type Stamp } from "./Frame.tsx";

export type ProductCardProps = Stamp & {
  name: string;
  category: string;
  vendor: string;
  cells: readonly SpecCell[];
  sources: readonly SourceView[];
  specDefs: SpecDefinitions;
};

export const PRODUCT_NONE: ProductCardProps = { address: "", asOf: null, name: "", category: "", vendor: "", cells: [],
  sources: [], specDefs: {} };

export const ProductCard: FC<ProductCardProps> = ({ name, category, vendor, cells, sources, specDefs, ...stamp }) => (
  <Frame {...stamp}>
    <div className="h-full flex flex-col justify-center gap-6">
      <div className="space-y-2">
        <p className="font-mono text-caption text-muted">{category} · {vendor}</p>
        <p className={`${TYPE.display} break-words`}>{name}</p>
      </div>
      <SpecTable runs={[{ title: DEFAULT_MESSAGES.specSectionCore, cells }]} sources={sources} specDefs={specDefs}
        labels={DEFAULT_VALUE_LABELS} />
    </div>
  </Frame>
);
