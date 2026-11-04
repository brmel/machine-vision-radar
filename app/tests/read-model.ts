import { readFileSync } from "node:fs";
import { join } from "node:path";
import { vi } from "vitest";
import { FilesCatalogRepository } from "../src/adapters/read-model/files.ts";
import { READ_MODEL } from "./fixture.ts";

export function servedReader(): FilesCatalogRepository {
  vi.stubGlobal("fetch", async (url: string) => {
    try {
      return new Response(readFileSync(join(READ_MODEL, decodeURIComponent(url.replace(/^\/read-model\//, "")))),
        { status: 200 });
    } catch {
      return new Response("", { status: 404 });
    }
  });
  return new FilesCatalogRepository();
}
