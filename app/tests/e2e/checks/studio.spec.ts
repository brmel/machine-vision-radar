import { mkdtempSync, readdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test, expect } from "@playwright/test";
import { filesReadModel } from "../../../scripts/head.ts";
import { parseScript, seconds, shown, unheld } from "../../../studio/clips/script.ts";
import { facts, TEMPLATES } from "../../../studio/clips/templates.ts";
import { record } from "../../../studio/footage/record.ts";
import { category, index, news } from "../sample.ts";

const repo = filesReadModel(join(process.env.MVR_E2E_FIXTURE ?? "", "dist", "public"));
const [product] = index.products.filter((p) => p.category === category.id);
const IDS = { product: product.id, compare: product.id, ask: product.id, vendor: product.vendor,
  article: news.items[0].slug, catalog: undefined } satisfies
  Record<keyof typeof TEMPLATES, string | undefined>;
const size = (file: string): number[] => [readFileSync(file).readUInt32BE(16), readFileSync(file).readUInt32BE(20)];

for (const [name, id] of Object.entries(IDS)) {
  test(`the ${name} template fills from the fixture and its flow is recorded on the built site`, async ({}, info) => {
    const template = Object.entries(TEMPLATES).find(([n]) => n === name)?.[1];
    if (!template) throw new Error(`no template ${name}`);
    const { steps, script } = await template(repo, id);
    expect(parseScript(JSON.parse(JSON.stringify(script)))).toEqual(script);
    expect(seconds(script)).toBeGreaterThanOrEqual(15);
    expect(seconds(script)).toBeLessThanOrEqual(30);
    expect(unheld(shown(script), await facts(repo, script.about))).toEqual([]);
    const folder = mkdtempSync(join(tmpdir(), "mvr-studio-"));
    await record(steps.filter((step) => !("hold" in step)), folder, info.project.use.baseURL ?? "");
    for (const [shot, width, height] of [["1920x1080", 1920, 1080], ["1080x1350", 1080, 1350]] as const) {
      expect(readFileSync(join(folder, `footage-${shot}.webm`)).length).toBeGreaterThan(10_000);
      expect(JSON.parse(readFileSync(join(folder, `footage-${shot}.json`), "utf8")).lead).toBeGreaterThan(0);
      const stills = readdirSync(folder).filter((f) => f.startsWith(`footage-${shot}-`)).map((f) => join(folder, f));
      expect(stills.length).toBeGreaterThan(0);
      for (const still of stills) expect(size(still)).toEqual([width, height]);
    }
  });
}
