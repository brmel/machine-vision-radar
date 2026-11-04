import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

const RECORD = join(import.meta.dirname, "..", "..", "scripts", "gates", "record-pass.sh");
const LIMITS = join(import.meta.dirname, "..", "..", "scripts", "limits.sh");

const ENV = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith("GIT_")));

describe("the gate's pass stamp", () => {
  let repo: string;
  const git = (...args: string[]) => execFileSync("git", args, { cwd: repo, encoding: "utf8", env: ENV }).trim();
  const commit = (content: string) => {
    writeFileSync(join(repo, "file.txt"), content);
    git("add", "file.txt");
    git("-c", "user.name=Gate Test", "-c", "user.email=gate@example.com", "commit", "-q", "-m", content);
    return git("rev-parse", "HEAD^{tree}");
  };
  const record = (tree: string) => spawnSync("bash", [RECORD, tree], { cwd: repo, encoding: "utf8", env: ENV });
  const stamp = () => join(repo, ".git", "mvradar-gates-pass");

  beforeEach(() => {
    repo = mkdtempSync(join(tmpdir(), "mvr-gate-pass-"));
    git("init", "-q");
  });
  afterEach(() => rmSync(repo, { recursive: true, force: true }));

  it("records the tree the run started on when it is still checked out and clean", () => {
    const tree = commit("first");
    expect(record(tree).status).toBe(0);
    expect(readFileSync(stamp(), "utf8").trim()).toBe(`${tree} ${process.version}`);
  });

  it.each([
    ["a commit landed", () => commit("second")],
    ["the tree was edited", () => writeFileSync(join(repo, "file.txt"), "edited")],
  ])("records nothing when %s during the run", (_change, change) => {
    const started = commit("first");
    change();
    const run = record(started);
    expect(run.status).toBe(0);
    expect(run.stderr).toContain("the pass is not recorded");
    expect(existsSync(stamp())).toBe(false);
  });
});

describe("a time-boxed step", () => {
  const timed = (limit: number, ...step: string[]) =>
    spawnSync("bash", ["-c", `source "$1"; shift; timed ${limit} step "$@"`, "_", LIMITS, ...step],
      { encoding: "utf8", timeout: 30_000 });

  it("passes within its limit and says how long it took", () => {
    const run = timed(5, "bash", "-c", "exit 0");
    expect(run.status).toBe(0);
    expect(run.stderr).toMatch(/--- step: \d+ s of 5 s/);
  });

  it("past its limit, stops the step and what the step started, and exits 142", () => {
    const pids = join(mkdtempSync(join(tmpdir(), "mvr-timed-")), "pids");
    const run = timed(1, "bash", "-c", `sleep 30 & echo $! > ${pids}; wait`);
    expect(run.status).toBe(142);
    expect(run.stderr).toContain("TIMEOUT: step ran past 1 s");
    const started = Number(readFileSync(pids, "utf8"));
    expect(() => process.kill(started, 0)).toThrow();
  }, 20_000);

  it("asks first with SIGINT, so a step stops what it started in a group of its own, as Playwright and Firebase "
    + "do", () => {
    const pids = join(mkdtempSync(join(tmpdir(), "mvr-timed-")), "pids");
    const step = `const c = require("node:child_process").spawn("sleep", ["30"], { detached: true });
      require("node:fs").writeFileSync(${JSON.stringify(pids)}, String(c.pid));
      process.on("SIGINT", () => { process.kill(-c.pid); process.exit(130); });
      setInterval(() => {}, 1000);`;
    const run = timed(1, "node", "-e", step);
    expect(run.status).toBe(142);
    expect(() => process.kill(Number(readFileSync(pids, "utf8")), 0)).toThrow();
  }, 20_000);
});
