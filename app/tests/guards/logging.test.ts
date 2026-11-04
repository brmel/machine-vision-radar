import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LOG_RULES, logger } from "../../src/shell/logger.ts";
import { APP, filesUnder, findings, isNode, lines, type AstNode } from "./source.ts";

const isCatchCall = (node: AstNode): boolean => node.type === "CallExpression" && isNode(node.callee) &&
  node.callee.type === "MemberExpression" && isNode(node.callee.property) && node.callee.property.name === "catch";

function swallowingLines(file: string, source: string): number[] {
  const handles = (node: unknown): boolean =>
    isNode(node) && /\blogger\.\w+\(|\bthrow\b/.test(source.slice(Number(node.start), Number(node.end)));
  return lines(file, source, (node) =>
    node.type === "CatchClause" ? !handles(node) : isCatchCall(node) && Array.isArray(node.arguments)
      && !handles(node.arguments[0]));
}

function consoleLines(file: string, source: string): number[] {
  return lines(file, source, (node) => node.type === "MemberExpression" && isNode(node.object) &&
    (node.object.name === "console" || (isNode(node.object.property) && node.object.property.name === "console")));
}

describe("no swallowed errors", () => {
  it("fires on a fixture that swallows errors", () => {
    const fixture = [
      "try { a(); } catch { /* ignore */ }",
      "try { a(); } catch (e) { setError(true); }",
      "p.catch(() => setError(true));",
      "try { a(); } catch (e) { logger.warn('a failed', {}, e); }",
      "try { a(); } catch (e) { throw new Error('wrapped', { cause: e }); }",
      "p.catch((e) => logger.error('load failed', {}, e));",
    ].join("\n");
    expect(swallowingLines("fixture.ts", fixture)).toEqual([1, 2, 3]);
  });

  it("finds no swallowed error in app/src", () => {
    expect(findings(filesUnder(["src", "studio"], /\.tsx?$/), swallowingLines)).toEqual([]);
  });
});

describe("one logger", () => {
  afterEach(() => vi.restoreAllMocks());

  it("fires on a fixture that calls console", () => {
    const fixture = ["console.log('x');", "logger.warn('degraded', {});", "window.console.error(e);",
      "const c = console;"].join("\n");
    expect(consoleLines("fixture.ts", fixture)).toEqual([1, 3]);
  });

  it("finds no console call in app/src or app/scripts outside the logger", () => {
    const paths = filesUnder(["src", "scripts", "studio"], /\.tsx?$/)
      .filter((path) => path !== join("src", "shell", "logger.ts"));
    expect(findings(paths, consoleLines)).toEqual([]);
  });

  it("follows the logging contract the Python logger reads", () => {
    expect(LOG_RULES).toEqual(JSON.parse(readFileSync(join(APP, "..", "contracts", "logging.json"), "utf8")));
  });

  it("writes JSON lines with the shared fields and no secret of any kind", () => {
    const secrets = {
      token: "s3cr3t-token-value",
      Authorization: "Bearer abc.def.ghi",
      cookie: "session=abc123",
      api_key: "AIzaSyA1234567890abcdefghijklmnopqrstuv",
      agent_token: "mvr_0123456789abcdefghijklmnop",
    };
    const lines: string[] = [];
    vi.spyOn(console, "warn").mockImplementation((line: string) => void lines.push(line));
    logger.warn("an ask failed with Bearer ya29.a0AfH6SMBx and eyJhbGciOi.eyJzdWIiOi.SflKxwRJSM",
      { ...secrets, product: "prd_0001" });
    const line = JSON.parse(lines[0]);
    expect(Object.keys(line).slice(0, 4)).toEqual(LOG_RULES.fields);
    expect(line.product).toBe("prd_0001");
    for (const secret of [...Object.values(secrets), "ya29.a0AfH6SMBx", "eyJhbGciOi"]) expect(lines[0])
      .not.toContain(secret);
  });
});
