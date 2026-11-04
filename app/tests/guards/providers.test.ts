import { execFileSync } from "node:child_process";
import { copyFileSync, cpSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { APP, filesUnder, findings, isNode, lines } from "./source.ts";

function cruise(file: string, source: string): string {
  const root = mkdtempSync(join(tmpdir(), "mvr-depcruise-"));
  copyFileSync(join(APP, ".dependency-cruiser.json"), join(root, ".dependency-cruiser.json"));
  cpSync(join(APP, "node_modules", "@firebase", "app"), join(root, "node_modules", "@firebase", "app"),
    { recursive: true });
  mkdirSync(join(root, file, ".."), { recursive: true });
  writeFileSync(join(root, file), source);
  try {
    execFileSync(join(APP, "node_modules", ".bin", "depcruise"), ["--config", ".dependency-cruiser.json", file],
      { cwd: root, encoding: "utf8", stdio: "pipe" });
    return "";
  } catch (err) {
    return String((err as { stdout?: string }).stdout);
  }
}

describe("storage providers stay in adapters/", () => {
  it.each([
    ["src/domain/ports/Leak.ts", "@firebase/app", "initializeApp"],
    ["src/features/leak/Leak.ts", "@google/genai", "GoogleGenAI"],
  ])("fails depcruise when %s imports %s", (file, pkg, name) => {
    expect(cruise(file, `import { ${name} } from "${pkg}";\nexport const leak = ${name};\n`))
      .toMatch(/adapters-own-providers/);
  });
});

function fetchLines(file: string, source: string): number[] {
  return lines(file, source, (node) => node.type === "CallExpression" && isNode(node.callee) &&
    (node.callee.name === "fetch" || (isNode(node.callee.property) && node.callee.property.name === "fetch")));
}

describe("raw HTTP stays in adapters/", () => {
  it("fires on a fixture that fetches", () => {
    expect(fetchLines("fixture.ts",
      "await fetch('https://example.com');\nwindow.fetch(url);\nconst f = repository.read(id);\n")).toEqual([1, 2]);
  });

  it("finds no fetch in app/src outside adapters/", () => {
    const paths = filesUnder(["src"], /\.tsx?$/).filter((path) => !path.startsWith(join("src", "adapters")));
    expect(findings(paths, fetchLines)).toEqual([]);
  });
});
