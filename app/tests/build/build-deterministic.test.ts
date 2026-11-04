import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const APP = join(import.meta.dirname, "..", "..");
const DIST = join(APP, "dist");

function fakeClock(iso: string): string {
  const source =
    `const Real = Date; const offset = Real.parse(${JSON.stringify(iso)}) - Real.now();` +
    `globalThis.Date = class extends Real { constructor(...a) { super(...(a.length ? a : [Real.now() + offset])); }` +
    ` static now() { return Real.now() + offset; } };`;
  return `data:text/javascript,${encodeURIComponent(source)}`;
}

const BUILD_ENV =
  Object.fromEntries(Object.entries(process.env).filter(([k]) => k !== "NODE_ENV" && !k.startsWith("VITEST")));

function buildAt(iso: string): Map<string, Buffer> {
  execFileSync("npm", ["run", "build"], {
    cwd: APP,
    env: { ...BUILD_ENV, NODE_OPTIONS: `--import=${fakeClock(iso)}` },
    stdio: "pipe",
  });
  const built = readdirSync(DIST, { recursive: true, withFileTypes: true }).filter((e) => e.isFile())
    .map((e) => join(e.parentPath, e.name));
  return new Map(built.map((f) => [relative(DIST, f), readFileSync(f)]));
}

describe("production build", () => {
  it.skipIf(!process.env.MVR_EMULATOR_GATE)("is byte-identical under two fake dates", () => {
    const early = buildAt("2001-02-03T04:05:06Z");
    const late = buildAt("2033-04-05T06:07:08Z");
    expect([...late.keys()].sort()).toEqual([...early.keys()].sort());
    const differing = [...early].filter(([file, bytes]) => !late.get(file)?.equals(bytes)).map(([file]) => file);
    expect(differing).toEqual([]);
  }, 240_000);
});
