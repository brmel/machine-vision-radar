import { defineConfig, devices } from "@playwright/test";

const smokeBaseUrl = process.env.SMOKE_BASE_URL;

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: smokeBaseUrl ? "**/smoke.spec.ts" : undefined,
  testIgnore: smokeBaseUrl ? "**/emulator/**" : ["**/smoke.spec.ts", "**/emulator/**"],
  snapshotPathTemplate: "{testDir}/baselines/{arg}-{platform}{ext}",
  fullyParallel: true,
  reporter: "list",
  use: { baseURL: smokeBaseUrl ?? "http://127.0.0.1:4173" },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: smokeBaseUrl
    ? undefined
    : {
        command: "npx vite preview --host 127.0.0.1 --port 4173 --strictPort",
        url: "http://127.0.0.1:4173",
        reuseExistingServer: false,
        timeout: 120_000,
      },
});
