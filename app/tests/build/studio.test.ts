import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { READ_MODEL, readView } from "../fixture.ts";
import type { IndexView, ProductView, RegistryView } from "../../src/domain/views.ts";

const APP = join(import.meta.dirname, "..", "..");

function still(...args: string[]): string {
  const out = mkdtempSync(join(tmpdir(), "mvr-studio-"));
  execFileSync("node", ["--experimental-strip-types", "studio/render.ts", "still", ...args], {
    cwd: APP, stdio: "pipe", env: { ...process.env, MVR_READ_MODEL_DIR: READ_MODEL, MVR_STUDIO_OUT: out },
  });
  return out;
}

const size = (file: string): [number, number] => {
  const png = readFileSync(file);
  return [png.readUInt32BE(16), png.readUInt32BE(20)];
};

describe("brand studio", () => {
  it("renders the catalog's card at both sizes from the registry's counts and date", () => {
    const out = join(still("catalog"), "catalog");
    const registry = readView<RegistryView>("registry.json");
    for (const [w, h] of [[1200, 627], [1080, 1350]]) {
      expect(size(join(out, `card-${w}x${h}.png`))).toEqual([w, h]);
      const drawn = JSON.parse(readFileSync(join(out, `card-${w}x${h}.json`), "utf8"));
      expect([drawn.counts, drawn.asOf]).toEqual([registry.counts, registry.data_as_of ?? null]);
    }
  }, 120_000);

  it("renders a product's card with its published key specifications and their sources, as many as fit", () => {
    const { products } = readView<IndexView>("index.json");
    const view = readView<ProductView>(`products/${products[0].id}.json`);
    const out = join(still("product", view.slug), `product-${view.slug}`);
    const published = view.core.filter((c) => c.value !== undefined);
    for (const [w, h, rows] of [[1200, 627, 4], [1080, 1350, 12]]) {
      expect(size(join(out, `card-${w}x${h}.png`))).toEqual([w, h]);
      const drawn = JSON.parse(readFileSync(join(out, `card-${w}x${h}.json`), "utf8"));
      expect([drawn.name, drawn.vendor, drawn.cells, drawn.sources])
        .toEqual([view.name, view.vendor.name, published.slice(0, rows), view.sources]);
    }
  }, 120_000);

  it("renders a post's clip from its card, its hook, caption and end card, with its SubRip captions", async () => {
    const out = join(still("catalog"), "catalog");
    writeFileSync(join(out, "script.json"), JSON.stringify({ hook: "The catalog, counted.",
      segments: [{ shows: "card", caption: "Every product, vendor and category it holds.", seconds: 1 }] }));
    execFileSync("node", ["--experimental-strip-types", "studio/render.ts", "clip", out, "square"], {
      cwd: APP, stdio: "pipe", env: { ...process.env, MVR_READ_MODEL_DIR: READ_MODEL, MVR_STUDIO_OUT: out },
    });
    const { getVideoMetadata } = await import("@remotion/renderer");
    const video = await getVideoMetadata(join(out, "clip-1080x1080.mp4"));
    expect([video.width, video.height, video.durationInSeconds]).toEqual([1080, 1080, 5.5]);
    expect(readFileSync(join(out, "clip-1080x1080.srt"), "utf8")).toBe(
      "1\n00:00:00,000 --> 00:00:02,000\nThe catalog, counted.\n\n2\n00:00:02,000 --> 00:00:03,000\nEvery product, "
        + "vendor and category it holds.\n");
  }, 120_000);

  it("refuses a clip or a post stating a figure no record it is about holds, and passes one that quotes the "
    + "records", () => {
    const out = mkdtempSync(join(tmpdir(), "mvr-studio-"));
    const { counts } = readView<RegistryView>("registry.json");
    const env = { ...process.env, MVR_READ_MODEL_DIR: READ_MODEL, MVR_STUDIO_OUT: out };
    const run = (...args: string[]) => execFileSync("node", ["--experimental-strip-types", "studio/render.ts", ...args],
      { cwd: APP, stdio: "pipe", env });
    writeFileSync(join(out, "script.json"), JSON.stringify({ hook: "999 products, counted.",
      segments: [{ shows: "card", caption: "Its counts.", seconds: 1 }] }));
    expect(() => run("clip", out, "square")).toThrow(/states 999, which no record it is about holds/);
    writeFileSync(join(out, "post.md"), `A seamless catalog of 999 products.`);
    expect(() => run("check", out)).toThrow(/2 finding/);
    writeFileSync(join(out, "post.md"),
      `The catalog holds ${counts.products} products from ${counts.organizations} vendors.`);
    expect(() => run("check", out)).not.toThrow();
  }, 60_000);

  it("refuses a script that runs long, shows what its post has not made or says a word the radar never "
    + "writes", async () => {
    const { parseScript, unheld } = await import("../../studio/clips/script.ts");
    const segment = { shows: "card", caption: "Its counts.", seconds: 10 };
    expect(() => parseScript({ hook: "The catalog.",
      segments: [segment, { ...segment, shows: "footage", seconds: 20 }] })).toThrow(/at most 30 s/);
    expect(() => parseScript({ hook: "The catalog.", segments: [segment, segment] })).toThrow(/each once/);
    expect(() => parseScript({ hook: "The catalog.", segments: [{ ...segment, shows: "catalog" }] }))
      .toThrow(/shows footage or card/);
    expect(() => parseScript({ hook: "A seamless catalog.", segments: [segment] })).toThrow(/the hook says "seamless"/);
    expect(parseScript({ hook: "Acme Instruments", segments: [segment] }).hook).toBe("Acme Instruments");
    expect(unheld("1,024 pixels of 3.45 µm, 12 bits", "[1024, 3.45, 10]")).toEqual(["12"]);
    expect(parseScript({ hook: "The catalog.", segments: [segment] }).segments).toEqual([segment]);
  });

  it("refuses a product the read model does not hold", () => {
    expect(() => still("product", "no-such__product")).toThrow(/holds no product no-such__product/);
  }, 60_000);
});
