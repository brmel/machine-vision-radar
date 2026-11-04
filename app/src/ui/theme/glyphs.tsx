import { type FC, type ReactNode } from "react";

type Glyph = FC<{ className: string }>;

export const RadarSweepGlyph: Glyph = ({ className }) => (
  <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
    <circle cx="16" cy="16" r="14" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.3" />
    <circle cx="16" cy="16" r="9" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.5" />
    <circle cx="16" cy="16" r="4" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.8" />
    <line x1="16" y1="2" x2="16" y2="30" stroke="currentColor" strokeWidth="1.2" strokeOpacity="0.3"
      strokeDasharray="2 2" />
    <line x1="2" y1="16" x2="30" y2="16" stroke="currentColor" strokeWidth="1.2" strokeOpacity="0.3"
      strokeDasharray="2 2" />
    <path d="M16 16 L28 10 A14 14 0 0 0 24 4 Z" fill="var(--color-accent)" fillOpacity="0.85" />
    <circle cx="21" cy="9" r="1.5" fill="var(--color-on-accent)" />
  </svg>
);

function drawn(box: 24 | 32, drawing: ReactNode): Glyph {
  return ({ className }) => (
    <svg viewBox={`0 0 ${box} ${box}`} fill="none" stroke="currentColor" strokeWidth="1.5" className={className}
      aria-hidden="true">
      {drawing}
    </svg>
  );
}

const GLYPHS: Readonly<Record<string, Glyph>> = {
  matrix: drawn(32, <>
    <rect x="4" y="6" width="24" height="20" rx="2" />
    <circle cx="16" cy="16" r="6" />
    <circle cx="16" cy="16" r="2" fill="currentColor" />
    <line x1="20" y1="9" x2="24" y2="9" />
  </>),
  depth: drawn(32, <>
    <path d="M16 4 L28 10 L16 16 L4 10 Z" />
    <path d="M4 10 L4 22 L16 28 L28 22 L28 10" />
    <path d="M16 16 L16 28" />
  </>),
  heat: drawn(32, <>
    <circle cx="16" cy="16" r="11" />
    <path d="M16 10 C14 12, 12 14, 12 17 C12 19.2, 13.8 21, 16 21 C18.2 21, 20 19.2, 20 17 C20 14, 18 12, 16 10 Z"
      fill="currentColor" fillOpacity="0.25" />
    <line x1="16" y1="2" x2="16" y2="5" />
    <line x1="16" y1="27" x2="16" y2="30" />
  </>),
  lens: drawn(32, <>
    <ellipse cx="16" cy="16" rx="10" ry="12" />
    <line x1="16" y1="4" x2="16" y2="28" strokeDasharray="2 2" />
    <path d="M6 16 Q16 10 26 16" />
    <path d="M6 16 Q16 22 26 16" />
  </>),
  chip: drawn(32, <>
    <rect x="5" y="5" width="22" height="22" rx="3" />
    <rect x="10" y="10" width="12" height="12" rx="1" fill="currentColor" fillOpacity="0.15" />
    <path d="M13 16h6M16 13v6" />
  </>),
  code: drawn(32, <>
    <rect x="4" y="6" width="24" height="20" rx="3" />
    <line x1="4" y1="12" x2="28" y2="12" />
    <circle cx="8" cy="9" r="1" fill="currentColor" />
    <circle cx="12" cy="9" r="1" fill="currentColor" />
    <path d="M10 18l3 3-3 3M17 24h5" />
  </>),
  cell: drawn(32, <>
    <circle cx="16" cy="16" r="11" />
    <circle cx="16" cy="16" r="6" strokeDasharray="3 2" />
    <line x1="16" y1="2" x2="16" y2="8" />
    <line x1="16" y1="24" x2="16" y2="30" />
    <line x1="2" y1="16" x2="8" y2="16" />
    <line x1="24" y1="16" x2="30" y2="16" />
  </>),
  connector: drawn(32, <>
    <rect x="6" y="8" width="20" height="16" rx="2" />
    <line x1="10" y1="24" x2="10" y2="28" />
    <line x1="22" y1="24" x2="22" y2="28" />
    <line x1="16" y1="24" x2="16" y2="28" />
    <circle cx="16" cy="14" r="3" />
  </>),
};

export const GLYPH_IDS: readonly string[] = Object.keys(GLYPHS);

export function glyphFor(id: string): Glyph {
  const glyph = GLYPHS[id];
  if (!glyph) throw new Error(`glyphFor: '${id}' is not in the glyph set`);
  return glyph;
}
