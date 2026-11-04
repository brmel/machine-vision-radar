import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";
import { play, type Step } from "./flows.ts";

const SHOTS = [
  { name: "1920x1080", viewport: { width: 1920, height: 1080 }, scale: 1 },
  { name: "1080x1350", viewport: { width: 540, height: 675 }, scale: 2 },
] as const;

export async function record(steps: readonly Step[], folder: string, base: string): Promise<void> {
  const browser = await chromium.launch();
  for (const shot of SHOTS) {
    const context = await browser.newContext({ baseURL: base, viewport: shot.viewport, deviceScaleFactor: shot.scale,
      recordVideo: { dir: folder, size: shot.viewport } });
    const page = await context.newPage();
    const prefix = path.join(folder, `footage-${shot.name}`);
    const { shown } = await play(page, steps, prefix);
    await context.close();
    const video = page.video();
    if (!video) throw new Error("studio: the browser recorded no video");
    fs.renameSync(await video.path(), `${prefix}.webm`);
    fs.writeFileSync(`${prefix}.json`, `${JSON.stringify({ lead: shown })}\n`);
  }
  await browser.close();
}
