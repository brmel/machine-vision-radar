// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import config from "../../../contracts/languages.json" with { type: "json" };
import { parseLanguages } from "../../src/domain/languages.ts";
import { MESSAGES } from "../../src/shell/i18n/index.tsx";
import { DEFAULT_MESSAGES, type Messages } from "../../src/shell/i18n/messages.ts";
import { localized } from "../../src/ui/specs/specFormat.ts";
import App from "../../src/shell/root/App.tsx";
import { browserStart } from "../../src/shell/root/start.ts";
import type { Route } from "../../src/shell/routing/routes.ts";
import { routeFromPath, pathFromRoute } from "../../src/shell/routing/router.ts";
import { servedReader } from "../read-model.ts";

const widgets = { name: "category", category: "example.widgets", query: "finish=matte,gloss" } as const;
const ROUTES: [string, string, Route, string?][] = [
  ["/", "", { name: "home" }],
  ["/browse", "", { name: "browse", query: "" }],
  ["/browse", "?stage=assemble", { name: "browse", query: "stage=assemble" }],
  ["/browse", "?category=example.widgets&finish=matte,gloss", widgets, "/category/example.widgets?finish=matte,gloss"],
  ["/category/example.widgets", "?finish=matte,gloss", widgets],
  ["/category/example.widgets", "", { ...widgets, query: "" }],
  ["/category/", "", { name: "not-found", path: "/category/" }],
  ["/product/widget-two", "", { name: "product-detail", productId: "widget-two" }],
  ["/product/widget-two/history", "", { name: "product-history", productId: "widget-two" }],
  ["/product/widget-two/specs", "", { name: "not-found", path: "/product/widget-two/specs" }],
  ["/vendor/example-devices", "", { name: "vendor-detail", vendorSlug: "example-devices", page: 1 }],
  ["/vendor/example-devices", "?page=3", { name: "vendor-detail", vendorSlug: "example-devices", page: 3 }],
  ["/vendor/example-devices", "?page=zero", { name: "vendor-detail", vendorSlug: "example-devices", page: 1 },
    "/vendor/example-devices"],
  ["/search", "", { name: "search", ask: "" }],
  ["/search", "?ask=Quel%20widget%20%3F", { name: "search", ask: "Quel widget ?" }],
  ["/news", "", { name: "news", query: "" }],
  ["/news", "?kind=article&page=2", { name: "news", query: "kind=article&page=2" }],
  ["/news/first-words", "", { name: "article", slug: "first-words" }],
  ["/news/first-words/more", "", { name: "not-found", path: "/news/first-words/more" }],
  ["/compare", "?ids=a,b&diff=1", { name: "compare", query: "ids=a,b&diff=1" }],
  ["/about", "", { name: "about" }],
  ["/non-existent", "", { name: "not-found", path: "/non-existent" }],
];

describe("browser-history routing", () => {
  it.each(ROUTES)("%s%s is its route and back", (path, search, route, back) => {
    expect(routeFromPath(path, search)).toEqual(route);
    expect(pathFromRoute(route)).toBe(back ?? `${path}${search}`);
  });
});

const FIXTURE = { code: "de", label: "DE", name: "Deutsch", dir: "ltr", intl: "de-DE", default: false };
// Justification (typed boundary): the pseudo-translation keeps every key of the default language's file.
const PSEUDO =
  Object.fromEntries(Object.entries(DEFAULT_MESSAGES).map(([key, text]) => [key, `⟦${text}⟧`])) as Messages;

describe("a third language", () => {
  it("renders from a config entry and a messages file, registry labels falling back to the catalog's own", async () => {
    const repository = servedReader();
    const { pipeline_stages: stages } = await repository.registry();
    window.history.pushState(null, "", "/");

    render(<App start={browserStart()} repository={repository} languages={parseLanguages([...config, FIXTURE])}
      messages={{ ...MESSAGES, de: PSEUDO }} />);
    fireEvent.click(await screen.findByRole("button", { name: FIXTURE.label }));

    expect(document.documentElement.lang).toBe("de");
    expect(await screen.findByRole("link", { name: PSEUDO.navBrowse })).toBeTruthy();
    expect(screen.getAllByText(localized(stages[0].label, "de")).length).toBeGreaterThan(0);
    expect(localized(stages[0].label, "de")).toBe(stages[0].label.en);
  });
});
