import { defineConfig, devices } from "@playwright/test";

const e2ePort = Number(process.env.E2E_PORT ?? "5174");
const hasExternalBaseUrl = Boolean(process.env.E2E_BASE_URL);
const baseURL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${e2ePort}`;
const apiURL = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";
const turnstileSiteKey = process.env.E2E_TURNSTILE_SITE_KEY ?? "";

export default defineConfig({
  testDir: "./e2e",
  // The app has several sizeable lazy-loaded workspaces. Serial browser
  // execution avoids treating Vite's cold transform of concurrent pages as a
  // product rendering failure, while keeping every assertion browser-real.
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "list" : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
    },
  ],
  // Use an isolated Vite port by default. Reusing a developer's existing server
  // can test a stale checkout rather than the source under test.
  webServer: hasExternalBaseUrl
    ? undefined
    : {
        command: `pnpm dev --host 127.0.0.1 --port ${e2ePort} --strictPort`,
        url: baseURL,
        env: { ...process.env, VITE_API_URL: apiURL, VITE_TURNSTILE_SITE_KEY: turnstileSiteKey },
        reuseExistingServer: process.env.E2E_REUSE_SERVER === "1",
        timeout: 120 * 1000,
      },
});
