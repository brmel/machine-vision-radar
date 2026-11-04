import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { DATA } from "../../scripts/head.ts";
import { GLYPH_IDS } from "../../src/ui/theme/glyphs.tsx";

// Justification (typed boundary): a registry vocabulary file; only the term ids are read.
const registry = JSON.parse(readFileSync(join(DATA, "registry/vocabularies/glyphs.json"), "utf8")) as
  { id: string }[];

describe("glyphs", () => {
  it("draws exactly the registry's glyph set", () => {
    expect([...GLYPH_IDS].sort()).toEqual(registry.map((g) => g.id).sort());
  });
});
