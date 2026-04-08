import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60000,
  use: {
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true,
  },
});
