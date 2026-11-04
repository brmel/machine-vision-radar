import { type FC } from "react";
import { RadarSweepGlyph } from "./glyphs.tsx";
import { BRAND_CONFIG } from "./brand.ts";
import { prevented } from "../controls/prevented.ts";

export const BrandLogo: FC<{ onHome: () => void }> = ({ onHome }) => (
  <a href="/" onClick={prevented(onHome)} className="inline-flex items-center gap-1.5 sm:gap-2.5 select-none group">
    <span className={"relative flex items-center justify-center w-7 h-7 sm:w-8 sm:h-8 rounded-chip bg-mark text-accent "
      + "transition-transform group-hover:scale-105"}>
      <RadarSweepGlyph className="w-4 h-4 sm:w-5 sm:h-5 text-on-mark" />
    </span>
    <span className="text-body sm:text-lead font-semibold tracking-tight text-fg leading-none whitespace-nowrap">
      <span className="sm:hidden">{BRAND_CONFIG.shortWordmark}</span>
      <span className="hidden sm:inline">{BRAND_CONFIG.wordmark}</span>
    </span>
  </a>
);
