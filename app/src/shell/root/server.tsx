import { renderToString } from "react-dom/server";
import type { CatalogRepository } from "../../domain/ports/CatalogRepository.ts";
import { PreparedReadsContext } from "../../ui/index.ts";
import App from "./App.tsx";
import { pathFromRoute } from "../routing/router.ts";
import type { Start } from "./start.ts";

const PASSES = 6;

export async function renderPage(start: Start, repository: CatalogRepository): Promise<string> {
  const values = new Map<string, unknown>();
  for (let pass = 0; pass < PASSES; pass++) {
    const asked = new Map<string, () => Promise<unknown>>();
    const ask = (key: string, read: () => Promise<unknown>) => {
      if (!asked.has(key)) asked.set(key, read);
    };
    const html = renderToString(
      <PreparedReadsContext.Provider value={{ values, ask }}>
        <App start={start} repository={repository} />
      </PreparedReadsContext.Provider>,
    );
    if (asked.size === 0) return html;
    for (const [key, value] of await Promise.all([...asked].map(async ([key, read]) => [key, await read()] as const)))
      values.set(key, value);
  }
  throw new Error(`renderPage: ${pathFromRoute(start.route)} still reads after ${PASSES} passes`);
}
