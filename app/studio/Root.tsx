import type { FC } from "react";
import { Composition } from "remotion";
import "../src/index.css";
import { CATALOG_NONE, CatalogCard } from "./cards/CatalogCard.tsx";
import { PRODUCT_NONE, ProductCard } from "./cards/ProductCard.tsx";
import { CLIP_NONE, Clip } from "./clips/Clip.tsx";
import { FPS, seconds } from "./clips/script.ts";
import { CLIP_SIZES, SIZES } from "./sizes.ts";

export const Root: FC = () => (
  <>
    {SIZES.map((size) => (
      <Composition key={`catalog-${size.name}`} id={`catalog-${size.name}`} component={CatalogCard}
        defaultProps={CATALOG_NONE} width={size.width} height={size.height} durationInFrames={1} fps={FPS} />
    ))}
    {CLIP_SIZES.map((size) => (
      <Composition key={`clip-${size.name}`} id={`clip-${size.name}`} component={Clip} defaultProps={CLIP_NONE}
        width={size.width} height={size.height} fps={FPS}
        durationInFrames={1}
        calculateMetadata={({ props }) => ({ durationInFrames: Math.round(seconds(props) * FPS) })} />
    ))}
    {SIZES.map((size) => (
      <Composition key={`product-${size.name}`} id={`product-${size.name}`} component={ProductCard}
        defaultProps={PRODUCT_NONE} width={size.width} height={size.height} durationInFrames={1} fps={FPS} />
    ))}
  </>
);
