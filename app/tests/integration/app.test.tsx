// @vitest-environment jsdom
import { describe, expect, it, afterEach, vi } from "vitest";
import { render, screen, act, cleanup, fireEvent } from "@testing-library/react";
import type { AuthGateway } from "../../src/domain/ports/review/AuthGateway.ts";
import { AuthProvider } from "../../src/shell/admin/AuthContext.tsx";
import { RequireAdmin } from "../../src/shell/admin/RequireAdmin.tsx";
import { I18nProvider } from "../../src/shell/i18n/index.tsx";
import { HttpReportInbox } from "../../src/adapters/review/HttpReportInbox.ts";
import { ReportError } from "../../src/features/product-detail/components/ReportError.tsx";
import { DEFAULT_MESSAGES as T } from "../../src/shell/i18n/messages.ts";

type App = { blocked: boolean };
const appCheck = vi.hoisted(() =>
  ({ options: [] as unknown[], minted: 0, down: false, blocked: false, apps: new Map<string, App>() }));
vi.mock("@firebase/app", () => ({
  initializeApp: (_config: unknown, name: string) => appCheck.apps.get(name)
    ?? appCheck.apps.set(name, { blocked: appCheck.blocked }).get(name),
}));
vi.mock("@firebase/app-check", () => ({
  ReCaptchaEnterpriseProvider: class { constructor(readonly siteKey: string) {} },
  initializeAppCheck: (app: App, options: unknown) => {
    if (appCheck.down) throw new Error("App Check did not load");
    return appCheck.options.push(options) && app;
  },
  getLimitedUseToken: (app: App) =>
    (app.blocked ? new Promise(() => undefined) : Promise.resolve({ token: `limited-${++appCheck.minted}` })),
}));

afterEach(() => {
  Object.assign(appCheck, { options: [], minted: 0, down: false, blocked: false, apps: new Map() });
  vi.useRealTimers();
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("RequireAdmin", () => {
  it("keeps the admin hidden when authentication is not configured, and says why", () => {
    const unconfigured: AuthGateway = {
      isConfigured: () => false, signIn: () => Promise.reject(new Error("not configured")),
      signOut: async () => undefined, idToken: async () => null, onAuthChange: () => () => undefined,
    };
    render(<I18nProvider><AuthProvider gateway={unconfigured}><RequireAdmin><div
      data-testid="protected-content">Secret</div></RequireAdmin></AuthProvider></I18nProvider>);
    expect(screen.queryByTestId("protected-content")).toBeNull();
    expect(screen.getByText(/Authentication is not configured/i)).toBeTruthy();
  });
});

describe("a reader's report", () => {
  const APP_CHECK = { apiKey: "key", projectId: "demo-mvradar", appId: "app", siteKey: "site-key" };

  it("goes to /api/report, each with an App Check token of its own when the build has the site key, and none without "
    + "it", async () => {
    const sent: { url: string; headers: Record<string, string>; body: unknown }[] = [];
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
      sent.push({ url, headers: init.headers as Record<string, string>, body: JSON.parse(String(init.body)) });
      return new Response(JSON.stringify({ report: sent.length === 1 ? "filed" : "counted" }),
        { status: sent.length === 1 ? 201 : 200 });
    });
    const report = { subject: "prd_0000000001", message: "The mass is 12 g on the datasheet.",
      sourceUrl: "https://example.com/datasheet.pdf" };
    const attested = new HttpReportInbox(APP_CHECK);
    attested.prepare();
    expect([await attested.report(report), await attested.report(report),
      await new HttpReportInbox(null).report(report)]).toEqual(["filed", "counted", "counted"]);
    expect(sent.map((s) => [s.url, s.headers["X-Firebase-AppCheck"]]))
      .toEqual([["/api/report", "limited-1"], ["/api/report", "limited-2"], ["/api/report", undefined]]);
    expect(sent[0].body).toEqual({ subject: report.subject, message: report.message, source_url: report.sourceUrl });
    expect(appCheck.options).toEqual([{ provider: { siteKey: "site-key" }, isTokenAutoRefreshEnabled: false }]);
  });

  it("shows the failed state when App Check fails to load or gives no token in time; the next report starts it "
    + "afresh", async () => {
    vi.useFakeTimers();
    const tokens: (string | undefined)[] = [];
    vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
      tokens.push((init.headers as Record<string, string>)["X-Firebase-AppCheck"]);
      return new Response(JSON.stringify({ report: "filed" }), { status: 201 });
    });
    appCheck.down = true;
    render(<I18nProvider><ReportError inbox={new HttpReportInbox(APP_CHECK)}
      subject="prd_0000000001" /></I18nProvider>);
    fireEvent.click(screen.getByRole("button", { name: T.reportErrorAction }));
    await act(() => vi.advanceTimersByTimeAsync(0));
    Object.assign(appCheck, { down: false, blocked: true });
    fireEvent.change(screen.getByLabelText(T.reportMessage, { exact: false }),
      { target: { value: "The mass is 12 g on the datasheet." } });
    fireEvent.click(screen.getByRole("button", { name: T.reportSend }));
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(screen.getByRole("status").textContent).toBe(T.reportFailed);
    appCheck.blocked = false;
    fireEvent.click(screen.getByRole("button", { name: T.reportSend }));
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(screen.getByRole("status").textContent).toBe(T.reportFiled);
    expect(tokens).toEqual(["limited-1"]);
  });

  it("names the protection and its owner's terms on the form only when the build has App Check", () => {
    for (const [config, links] of [[APP_CHECK,
      ["https://policies.google.com/privacy", "https://policies.google.com/terms"]], [null, []]] as const) {
      render(<I18nProvider><ReportError inbox={new HttpReportInbox(config)} subject="prd_0000000001" /></I18nProvider>);
      fireEvent.click(screen.getByRole("button", { name: T.reportErrorAction }));
      expect(screen.queryAllByRole("link").map((a) => a.getAttribute("href"))).toEqual(links);
      cleanup();
    }
  });
});
