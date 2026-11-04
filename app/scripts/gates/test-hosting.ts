import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { DEV } from "../head.ts";

const FIREBASE_JSON = path.join(DEV, "firebase.json");

interface Header { key: string; value: string }
interface Rule { source: string; headers: Header[] }
interface FirebaseJson {
  hosting: { headers: Rule[] };
  emulators: Record<string, unknown>;
}

// Justification (typed boundary): firebase.json is read once; only the fields above are used.
const read = (): FirebaseJson => JSON.parse(fs.readFileSync(FIREBASE_JSON, "utf-8")) as FirebaseJson;

const emulatorHosts = (fb: FirebaseJson): string[] =>
  Object.values(fb.emulators)
    .flatMap((e) => (typeof e === "object" && e && "port" in e && "host" in e ? [`http://${e.host}:${e.port}`] : []));

const withEmulators = (fb: FirebaseJson, h: Header): Header =>
  h.key === "Content-Security-Policy"
    ? { ...h, value: ["connect-src ", "frame-src ", "img-src "].reduce((csp, directive) =>
      csp.replace(directive, `${directive}${emulatorHosts(fb).join(" ")} `), h.value) }
    : h;

function globRegex(source: string): RegExp {
  const convert = (glob: string): string =>
    glob.replace(/\*\*|\*|\{([^}]*)\}|@\(([^)]*)\)|[.+?^$|()[\]\\]/g,
      (token, brace: string | undefined, at: string | undefined) => {
        if (token === "**") return ".*";
        if (token === "*") return "[^/]*";
        if (brace !== undefined) return `(?:${brace.split(",").map(convert).join("|")})`;
        if (at !== undefined) return `(?:${at.split("|").map(convert).join("|")})`;
        return `\\${token}`;
      });
  return new RegExp(`^${convert(source)}$`);
}

export function hostingHeaders(pathname: string, gates: boolean): Record<string, string> {
  const fb = read();
  return Object.fromEntries(fb.hosting.headers.filter((r) => globRegex(r.source).test(pathname))
    .flatMap((r) => r.headers.map((h) => (gates ? withEmulators(fb, h) : h))).map((h) => [h.key, h.value]));
}

const TEST_CONFIG = path.join(DEV, "firebase.gate.json");

if (process.argv[1] && fileURLToPath(import.meta.url) === fs.realpathSync(process.argv[1])) {
  const fb = read();
  const headers = fb.hosting.headers.map((r) => ({ ...r, headers: r.headers.map((h) => withEmulators(fb, h)) }));
  fs.writeFileSync(TEST_CONFIG, JSON.stringify({ ...fb, hosting: { ...fb.hosting, headers } }, null, 2));
}
