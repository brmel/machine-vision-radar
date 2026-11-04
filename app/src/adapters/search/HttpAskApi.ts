import type { AskApi, SearchEvent } from "../../domain/ports/AskApi.ts";
import type { AskAnswer } from "../../domain/views.ts";
import { AskAnswerSchema } from "../generated-views-zod.ts";
import { postJson } from "../http.ts";

export class HttpAskApi implements AskApi {
  private referred = true;

  async ask(question: string, locale: string): Promise<AskAnswer> {
    const res = await postJson("ask", { question, locale }, {}, [429, 503]);
    return AskAnswerSchema.parse(await res.json());
  }

  async count(event: SearchEvent): Promise<void> {
    const from = this.referred ? document.referrer : "";
    this.referred = false;
    await postJson("count", { event, ...(from ? { from } : {}) });
  }
}
