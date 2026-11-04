import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Page, Response } from "@playwright/test";

import { DATA, DEV } from "../scripts/head.ts";
export const READ_MODEL = join(process.env.MVR_E2E_FIXTURE ?? "", "dist", "public");

export function registryFile<T>(file: string): T {
  // Justification (typed boundary): a registry file; each caller reads only the fields its type names.
  return JSON.parse(readFileSync(join(process.env.MVR_E2E_FIXTURE ?? DATA, "registry", file), "utf8")) as T;
}

export function readView<T>(file: string): T {
  // Justification (typed boundary): the generated contract types the files; the zod schemas check them in the app.
  return JSON.parse(readFileSync(join(READ_MODEL, file), "utf8")) as T;
}

const FIRESTORE = `${process.env.FIRESTORE_EMULATOR_HOST ?? "127.0.0.1:8085"}/v1/`;

export function rows<T>(name: string, dir = process.env.MVR_E2E_FIXTURE ?? ""): T[] {
  // Justification (typed boundary): the fixture's rows as a spec types them; the fixture is validated when it is built.
  return readFileSync(join(dir, "data", name), "utf8").trim().split("\n").map((l) => JSON.parse(l) as T);
}

export function radar(...args: string[]): string {
  return execFileSync("python3", ["-m", "radar", ...args], {
    cwd: DEV, stdio: "pipe", encoding: "utf8",
    env: { ...process.env, MVR_DATA: process.env.MVR_E2E_FIXTURE ?? "" },
  });
}

function listedIn(answer: unknown): number[] {
  // Justification (typed boundary): a Firestore REST answer, a document or a runQuery list; only `fields.json` and
  const docs =
    (Array.isArray(answer) ? answer.map((r: { document?: unknown }) => r.document)
      : [answer]) as ({ fields?: { json?: { stringValue?: string }; card?: unknown } } | undefined)[];
  const queried = docs.filter((d) => d?.fields?.card !== undefined).length;
  return queried > 0 ? [queried] : docs.flatMap((d) => {
    const view: unknown = JSON.parse(d?.fields?.json?.stringValue ?? "null");
    if (Array.isArray(view)) return [view.length];
    const listing = view && typeof view === "object" && "products" in view ? view.products : undefined;
    return Array.isArray(listing) ? [listing.length] : [];
  });
}

export function watchReads(page: Page): { reads: string[]; listed: number[] } {
  const seen = { reads: [] as string[], listed: [] as number[] };
  page.on("request", (r) => {
    if (r.url().includes(FIRESTORE)) seen.reads.push(decodeURIComponent(r.url().split("/documents")[1] ?? r.url()));
  });
  page.on("response", async (res: Response) => {
    if (res.url().includes(FIRESTORE) && res.ok()) seen.listed.push(...listedIn(await res.json()));
  });
  return seen;
}

export function consoleErrors(page: Page, ignored?: RegExp): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !ignored?.test(msg.text())) errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  return errors;
}

declare global {
  interface Window {
    __cspViolations: string[];
  }
}

export const watchCsp = (page: Page): Promise<unknown> =>
  page.addInitScript(() => {
    window.__cspViolations = [];
    window.addEventListener("securitypolicyviolation",
      (e) => window.__cspViolations.push(`${e.effectiveDirective} blocked ${e.blockedURI} at `
        + `${e.sourceFile}:${e.lineNumber}`));
  });

export default function setup(): () => void {
  const run = mkdtempSync(join(tmpdir(), "mvr-vitest-"));
  process.env.TMPDIR = run;
  execFileSync("npm", ["run", "-s", "build:server"], { cwd: join(import.meta.dirname, ".."), stdio: "pipe" });
  if (!process.env.MVR_E2E_FIXTURE) {
    const out = mkdtempSync(join(run, "fixture-"));
    execFileSync("python3", ["-m", "radar.tests.fixtures.fixture_category", out, "16"], { cwd: DEV, stdio: "pipe" });
    process.env.MVR_E2E_FIXTURE = out;
  }
  return () => rmSync(run, { recursive: true, force: true });
}
