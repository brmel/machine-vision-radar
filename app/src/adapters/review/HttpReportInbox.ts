import { z } from "zod";
import { postJson } from "../http.ts";
import type { ErrorReport, Protection, ReportInbox } from "../../domain/ports/review/ReportInbox.ts";

export interface AppCheckConfig {
  readonly apiKey: string;
  readonly projectId: string;
  readonly appId: string;
  readonly siteKey: string;
}

type Mint = () => Promise<string>;
const Filed = z.object({ report: z.enum(["filed", "counted"]) });
const RECAPTCHA: Protection = { name: "reCAPTCHA", owner: "Google",
  links: ["https://policies.google.com/privacy", "https://policies.google.com/terms"] };
const TOKEN_LIMIT_MS = 10_000;

async function minter({ siteKey, ...web }: AppCheckConfig, name: string): Promise<Mint> {
  const [{ initializeApp }, { initializeAppCheck, getLimitedUseToken, ReCaptchaEnterpriseProvider }] =
    await Promise.all([import("@firebase/app"), import("@firebase/app-check")]);
  const appCheck = initializeAppCheck(initializeApp(web, name),
    { provider: new ReCaptchaEnterpriseProvider(siteKey), isTokenAutoRefreshEnabled: false });
  return async () => (await getLimitedUseToken(appCheck)).token;
}

export class HttpReportInbox implements ReportInbox {
  private mint: Promise<Mint> | null = null;
  private loads = 0;

  constructor(private readonly appCheck: AppCheckConfig | null) {}

  get protection(): Protection | null {
    return this.appCheck ? RECAPTCHA : null;
  }

  async prepare(): Promise<void> {
    await this.loaded();
  }

  async report({ subject, message, sourceUrl }: ErrorReport): Promise<"filed" | "counted"> {
    const token = await this.token();
    const res = await postJson("report", { subject, message, ...(sourceUrl ? { source_url: sourceUrl } : {}) },
      token ? { "X-Firebase-AppCheck": token } : {});
    return Filed.parse(await res.json()).report;
  }

  private loaded(): Promise<Mint> | null {
    if (!this.appCheck) return null;
    const mint: Promise<Mint> = this.mint ?? minter(this.appCheck, `app-check-${++this.loads}`)
      .catch((err: unknown) => {
      if (this.mint === mint) this.mint = null;
      throw err;
    });
    this.mint = mint;
    return mint;
  }

  private async token(): Promise<string | null> {
    const loaded = this.loaded();
    if (!loaded) return null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const late = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        if (this.mint === loaded) this.mint = null;
        reject(new Error(`no App Check token in ${TOKEN_LIMIT_MS} ms`));
      }, TOKEN_LIMIT_MS);
    });
    try {
      return await Promise.race([loaded.then((mint) => mint()), late]);
    } finally {
      clearTimeout(timer);
    }
  }
}
