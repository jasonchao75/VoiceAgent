import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.VOICE_AGENT_UI_URL || "http://127.0.0.1:8000";

export default defineConfig({
  testDir: "./tests/ui",
  outputDir: "../test-results/playwright",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { outputFolder: "../test-results/playwright-report", open: "never" }]],
  use: {
    baseURL,
    colorScheme: "dark",
    locale: "en-US",
    timezoneId: "UTC",
    reducedMotion: "reduce",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } },
    },
    {
      name: "narrow-chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1024, height: 1000 } },
    },
  ],
});
