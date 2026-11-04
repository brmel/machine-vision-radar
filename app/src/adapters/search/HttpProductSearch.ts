import type { ProductSearch } from "../../domain/ports/ProductSearch.ts";
import type { Found } from "../../domain/views.ts";
import { FoundSchema } from "../generated-views-zod.ts";
import { postJson } from "../http.ts";

export class HttpProductSearch implements ProductSearch {
  async search(words: string): Promise<Found> {
    return FoundSchema.parse(await (await postJson("find", { words })).json());
  }
}
