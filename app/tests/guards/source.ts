import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseAst } from "vite";

export const APP = join(import.meta.dirname, "..", "..");

export interface AstNode {
  readonly [key: string]: unknown;
}

export function isNode(value: unknown): value is AstNode {
  return typeof value === "object" && value !== null;
}

export function filesUnder(dirs: readonly string[], pattern: RegExp): string[] {
  return execFileSync("git", ["ls-files", "--cached", "--others", "--exclude-standard", "--", ...dirs],
    { cwd: APP, encoding: "utf8" })
    .split("\n").filter((path) => path && pattern.test(path));
}

export function lines(file: string, source: string, picks: (node: AstNode) => boolean): number[] {
  return nodes(file, source).filter(picks).map((node) => source.slice(0, Number(node.start)).split("\n").length);
}

export function nodes(file: string, source: string): AstNode[] {
  const found: AstNode[] = [];
  const visit = (value: unknown): void => {
    if (Array.isArray(value)) return value.forEach(visit);
    if (!isNode(value)) return;
    found.push(value);
    Object.values(value).forEach(visit);
  };
  visit(parseAst(source, { lang: file.endsWith(".tsx") ? "tsx" : "ts" }));
  return found;
}

export function findings(paths: readonly string[],
    find: (path: string, source: string) => readonly (number | string)[]): string[] {
  return paths.flatMap((path) => find(path, readFileSync(join(APP, path), "utf8"))
    .map((finding) => `${path}:${finding}`));
}
