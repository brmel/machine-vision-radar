import { readFileSync } from "node:fs";
import { test, expect, devices, type Browser, type Response } from "@playwright/test";
import { category, index } from "../sample.ts";

interface Budgets {
  first_load_js_kib: number;
  first_load_data_kib: Record<"home" | "category" | "product" | "news", number>;
  core_web_vitals: { lcp_ms: number; cls: number; tbt_ms: number };
}
// Justification (typed boundary): the budgets file sits next to package.json; only the fields above are read.
const BUDGETS = JSON.parse(readFileSync(new URL("../../../perf-budgets.json", import.meta.url), "utf8")) as Budgets;
const KIB = 1024;
const product = index.products.find((p) => p.category === category.id)!;
const PAGES = {
  home: { path: "/", reads: ["registry.json"] },
  category: {
    path: `/browse?category=${category.id}`,
    reads: ["organizations.json", "registry.json", `public_facets/${category.id}`,
      `public_facets/${category.id}/pages/1`, "public_index/news"],
  },
  product: { path: `/product/${product.slug}`, reads: ["registry.json", `public_products/${product.id}`] },
  news: { path: "/news", reads: ["registry.json", "public_index/news"] },
} as const;

const OBSERVE = `(() => { window.__lcp = 0; window.__cls = 0; window.__long = []; window.__fcp = 0;
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lcp = e.startTime; })
    .observe({ type: "largest-contentful-paint", buffered: true });
  new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
    .observe({ type: "layout-shift", buffered: true });
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long.push([e.startTime, e.duration]); })
    .observe({ type: "longtask", buffered: true });
  new PerformanceObserver((l) => {
    for (const e of l.getEntries()) if (e.name === "first-contentful-paint") window.__fcp = e.startTime;
  }).observe({ type: "paint", buffered: true });
})()`;

async function measure(browser: Browser, path: string) {
  const context = await browser.newContext({ ...devices["Pixel 5"] });
  const page = await context.newPage();
  await (await context.newCDPSession(page)).send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.addInitScript(OBSERVE);
  const bytes = { js: 0, data: 0 };
  const reads: string[] = [];
  const count = async (res: Response) => {
    const url = new URL(res.url()).pathname;
    const read = url.startsWith("/read-model/") ? url.slice("/read-model/".length) : url.split("/documents/")[1];
    const data = Boolean(read) && res.request().method() === "GET";
    if (!url.endsWith(".js") && !data) return;
    const { length } = await res.body();
    if (url.endsWith(".js")) bytes.js += length;
    if (data) {
      bytes.data += length;
      reads.push(decodeURIComponent(read));
    }
  };
  const counted: Promise<void>[] = [];
  const onResponse = (res: Response) => counted.push(count(res));
  page.on("response", onResponse);
  await page.goto(path, { waitUntil: "networkidle" });
  await page.waitForFunction("window.__lcp > 0");
  const vitals = await page.evaluate(async () => {
    await new Promise((idle) => requestIdleCallback(idle));
    // Justification (typed boundary): the observers above store their readings on window.
    const w = window as unknown as { __lcp: number; __cls: number; __fcp: number; __long: [number, number][] };
    return { lcp: w.__lcp, cls: w.__cls,
      tbt: w.__long.filter(([start]) => start >= w.__fcp).reduce((t, [, d]) => t + Math.max(0, d - 50), 0) };
  });
  page.off("response", onResponse);
  await Promise.all(counted);
  await context.close();
  return { bytes, reads: reads.sort(), vitals };
}

for (const [name, spec] of Object.entries(PAGES) as [keyof typeof PAGES, (typeof PAGES)[keyof typeof PAGES]][]) {
  test(`${name} stays within its budgets and reads only its own data`, async ({ browser }) => {
    const { bytes, reads, vitals } = await measure(browser, spec.path);
    expect(reads).toEqual([...spec.reads].sort());
    expect(bytes.js / KIB, "first-load JS (KiB)").toBeLessThanOrEqual(BUDGETS.first_load_js_kib);
    expect(bytes.data / KIB, "first-load data (KiB)").toBeLessThanOrEqual(BUDGETS.first_load_data_kib[name]);
    expect(vitals.lcp, "LCP (ms)").toBeLessThanOrEqual(BUDGETS.core_web_vitals.lcp_ms);
    expect(vitals.cls, "CLS").toBeLessThanOrEqual(BUDGETS.core_web_vitals.cls);
    expect(vitals.tbt, "TBT (ms)").toBeLessThanOrEqual(BUDGETS.core_web_vitals.tbt_ms);
    test.info().annotations.push({ type: "measured", description: JSON.stringify({ js_kib: +(bytes.js / KIB).toFixed(1),
      data_kib: +(bytes.data / KIB).toFixed(1), ...vitals }) });
  });
}
