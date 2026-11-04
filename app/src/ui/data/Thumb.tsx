import { type FC } from "react";
import { glyphFor } from "../theme/glyphs.tsx";

const SIZES = { sm: "w-10 h-10", md: "w-12 h-12" } as const;

export const Thumb: FC<{ url: string | undefined; glyph: string; size?: keyof typeof SIZES }> = ({ url, glyph,
  size = "sm" }) => {
  const Glyph = glyphFor(glyph);
  return (
    <div className={`${SIZES[size]} rounded-control border border-line bg-sunken flex items-center justify-center `
      + `shrink-0 text-fg-secondary overflow-hidden`}>
      {url ? <img src={url} alt="" className="w-full h-full object-cover" loading="lazy" width={48} height={48} />
        : <Glyph className="w-1/2 h-1/2" aria-hidden="true" />}
    </div>
  );
};
