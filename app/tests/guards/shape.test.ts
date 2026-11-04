import { parseAst } from "vite";
import { describe, expect, it } from "vitest";
import { type AstNode, filesUnder, findings, isNode, lines, nodes } from "./source.ts";

const OVER_TEN: Readonly<Record<string, string>> = {
  "src/shell/routing/RouteView.tsx:RouteView": "the exhaustive switch over the routes: a case per route, checked by "
    + "the compiler",
};

const anyLines = (file: string, source: string): number[] =>
  lines(file, source, (node) => node.type === "TSAnyKeyword");

const nameOf = (node: unknown): string => (isNode(node) ? String(node.name) : "");

function interfaceProblems(file: string, source: string): string[] {
  const all = nodes(file, source);
  const interfaces = all.filter((node) => node.type === "TSInterfaceDeclaration").map((node) => nameOf(node.id));
  const implemented =
    new Set(all.filter((node) => node.type === "TSClassImplements").map((node) => nameOf(node.expression)));
  return [
    ...interfaces.filter((name) => implemented.has(name))
      .map((name) => `${name} is declared and implemented in one file`),
    ...interfaces.filter((name) => /^I[A-Z]/.test(name)).map((name) => `${name} has an I prefix`),
  ];
}

describe("no any", () => {
  it("fires on a fixture that uses any", () => {
    const fixture = "const a: any = 1;\nfunction f(x: unknown) { return x as any; }\nlet b: Array<any>;\n";
    expect(anyLines("fixture.ts", fixture)).toEqual([1, 2, 3]);
    expect(anyLines("fixture.ts", "// any in a comment\nconst s = 'any';\n")).toEqual([]);
  });

  it("finds none in app/src, app/scripts and app/tests", () => {
    expect(findings(filesUnder(["src", "scripts", "studio", "tests"], /\.(ts|tsx|mts)$/), anyLines)).toEqual([]);
  });
});

describe("interfaces stand alone", () => {
  it("fires on a fixture that mixes an interface with its implementation", () => {
    const fixture =
      "export interface IStore { get(): number }\nexport class MemoryStore implements IStore { get() { return 1; } }\n";
    expect(interfaceProblems("fixture.ts", fixture))
      .toEqual(["IStore is declared and implemented in one file", "IStore has an I prefix"]);
    expect(interfaceProblems("fixture.ts",
      'import type { Store } from "./Store.ts";\nexport class MemoryStore implements Store { get() { return 1; } }\n'))
        .toEqual([]);
  });

  it("finds none in app/src and app/scripts", () => {
    expect(findings(filesUnder(["src", "scripts", "studio"], /\.tsx?$/), interfaceProblems)).toEqual([]);
  });
});

const FUNCTIONS = new Set(["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"]);
const BRANCHES =
  new Set(["IfStatement", "ConditionalExpression", "ForStatement", "ForInStatement", "ForOfStatement", "WhileStatement",
  "DoWhileStatement", "CatchClause", "LogicalExpression"]);
const LOGICAL_ASSIGNMENTS = new Set(["&&=", "||=", "??="]);

function branches(fn: AstNode): number {
  let n = 1;
  const visit = (value: unknown): void => {
    if (Array.isArray(value)) return value.forEach(visit);
    if (!isNode(value) || FUNCTIONS.has(String(value.type))) return;
    const branch = BRANCHES.has(String(value.type)) || (value.type === "SwitchCase" && value.test !== null) ||
      (value.type === "AssignmentExpression" && LOGICAL_ASSIGNMENTS.has(String(value.operator)));
    n += branch ? 1 : 0;
    Object.values(value).forEach(visit);
  };
  Object.values(fn).forEach(visit);
  return n;
}

function overTen(file: string, source: string): string[] {
  const out: string[] = [];
  const walk = (value: unknown, name: string, named: boolean): void => {
    if (Array.isArray(value)) return value.forEach((v) => walk(v, name, named));
    if (!isNode(value)) return;
    const fn = FUNCTIONS.has(String(value.type));
    const own = !fn ? name : isNode(value.id) ? String(value.id.name) : named ? name
      : `${name} > line ${source.slice(0, Number(value.start)).split("\n").length}`;
    if (fn && branches(value) > 10) out.push(own);
    for (const child of Object.values(value)) {
      const key = value.type === "VariableDeclarator" ? value.id : value.type === "MethodDefinition"
        || value.type === "Property" ? value.key : null;
      const keyed = isNode(key) && typeof key.name === "string";
      walk(child, keyed ? String(key.name) : own, keyed);
    }
  };
  walk(parseAst(source, { lang: file.endsWith(".tsx") ? "tsx" : "ts" }), "<module>", false);
  return out;
}

describe("functions within ten branches", () => {
  it("counts each branch, on a fixture", () => {
    const fixture =
      `function f(a, b) { if (a && b) return a ?? b; for (const x of a) while (x) x ||= 1; return a ? 1 : 2; }
const g = () => { switch (a) { case 1: return; case 2: return; default: } try {} catch {} };`;
    const [f, g] = nodes("fixture.ts", fixture).filter((n) => FUNCTIONS.has(String(n.type)));
    expect([branches(f), branches(g)]).toEqual([8, 4]);
  });

  it("finds none in app/src and app/scripts but the listed ones", () => {
    const over = findings(filesUnder(["src", "scripts", "studio"], /\.tsx?$/), overTen)
      .filter((f) => !f.includes("/generated-"));
    expect(over.filter((f) => !(f in OVER_TEN))).toEqual([]);
    expect(Object.keys(OVER_TEN).filter((f) => !over.includes(f))).toEqual([]);
  });
});
