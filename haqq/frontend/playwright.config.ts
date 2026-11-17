import { defineConfig } from "@playwright/test";

// Requires the API (with the DEMO dataset) on :8000 and `npm run dev` on :5173.
export default defineConfig({
  testDir: "e2e",
  timeout: 60000,
  use: { baseURL: process.env.HAQQ_UI_URL || "http://127.0.0.1:5173", trace: "off",
    launchOptions: process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {} },
});
