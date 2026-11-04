import type { FC, ReactNode } from "react";
import { AbsoluteFill, Img, staticFile, useVideoConfig } from "remotion";
import { BRAND_CONFIG } from "../../src/ui/theme/brand.ts";
import { TYPE } from "../../src/ui/index.ts";
import { DEFAULT_MESSAGES as messages, fill } from "../../src/shell/i18n/messages.ts";
import { formatDate } from "../../src/ui/specs/specFormat.ts";
import { DEFAULT_LANGUAGE } from "../../src/domain/languages.ts";

export type Stamp = {
  address: string;
  asOf: string | null;
};

export const Zoomed: FC<{ className: string; children: ReactNode }> = ({ className, children }) => {
  const { width, height } = useVideoConfig();
  const zoom = Math.min(width / 760, height / 600);
  return <div className={className} style={{ zoom, width: width / zoom, height: height / zoom }}>{children}</div>;
};

export const Frame: FC<Stamp & { children: ReactNode }> = ({ address, asOf, children }) => (
  <AbsoluteFill className="bg-page text-fg">
    <Zoomed className="p-10 flex flex-col gap-8">
      <header className="flex items-center gap-4">
        <Img src={staticFile("favicon.svg")} className="size-12 rounded-control" />
        <div>
          <p className={TYPE.section}>{BRAND_CONFIG.wordmark}</p>
          <p className="text-body text-muted">{BRAND_CONFIG.tagline}</p>
        </div>
      </header>
      <div className="flex-1 min-h-0">{children}</div>
      <footer className={"flex items-baseline justify-between gap-6 border-t border-line pt-4 font-mono text-caption "
        + "text-muted"}>
        <span>{address}</span>
        <span>{fill(messages.dataUpdatedLabel,
          { date: asOf ? formatDate(asOf, DEFAULT_LANGUAGE.code) : messages.unknownValue })}</span>
      </footer>
    </Zoomed>
  </AbsoluteFill>
);
