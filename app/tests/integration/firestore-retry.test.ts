import { afterEach, describe, expect, it, vi } from "vitest";
import { FirestoreCatalogRepository } from "../../src/adapters/read-model/firestore.ts";
import { readView } from "../fixture.ts";
import type { IndexView } from "../../src/domain/views.ts";

const { products } = readView<IndexView>("index.json");
const fields = { fields: { json: { stringValue: JSON.stringify(readView(`products/${products[0].id}.json`)) } } };

describe("the Firestore read model over a flaky network", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads a product after two refused connections, and gives up on the third", async () => {
    let calls = 0;
    vi.stubGlobal("fetch", vi.fn(async () => {
      calls += 1;
      if (calls < 3) throw new TypeError("fetch failed");
      return new Response(JSON.stringify(fields), { status: 200 });
    }));
    const repository = new FirestoreCatalogRepository("https://firestore.example/v1/projects/p/databases/d/documents");
    expect((await repository.product(products[0].id))?.id).toBe(products[0].id);
    expect(calls).toBe(3);

    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    await expect(new FirestoreCatalogRepository("https://firestore.example/v1/d").product(products[0].id))
      .rejects.toThrow("fetch failed");
  });
});
