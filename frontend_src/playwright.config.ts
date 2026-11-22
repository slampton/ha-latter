/**
 * Playwright Headless Chromium + `@axe-core/playwright` Configuration.
 *
 * - Serves `<latter-studio>` in-memory via `page.route("http://studio.local/**", ...)` with zero
 *   TCP port binding so tests run deterministically in ~50 ms inside Windows/Linux sandboxes.
 * - Writes transient test artifacts to `os.tmpdir()` so `ha-latter/` stays 100% free of scratch files.
 */

import { defineConfig } from "@playwright/test";
import os from "node:os";
import path from "node:path";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  outputDir: path.join(os.tmpdir(), "latter-studio-playwright-results"),
  globalTeardown: "./e2e/global-teardown.ts",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: process.env.CI ? 2 : 4,
  reporter: "list",
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    browserName: "chromium",
    headless: true,
    launchOptions: {
      args: [
        `--log-file=${path.join(os.tmpdir(), "latter-studio-chromium.log")}`,
        "--disable-logging",
        "--disable-gpu",
      ],
    },
    viewport: { width: 1440, height: 900 },
    actionTimeout: 10_000,
    trace: "off",
    screenshot: "off",
    video: "off",
  },
});
