/**
 * Playwright Global Teardown.
 *
 * Cleans up Windows Chromium ANGLE/Vulkan `debug.log` written to `frontend_src/` CWD so
 * `git status` and workspace hygiene gates stay 100% clean after every `playwright test` run.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export default function globalTeardown(): void {
  const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  try {
    fs.unlinkSync(path.join(frontendDir, "debug.log"));
  } catch {
    // Ignore if Chromium did not emit debug.log on this OS.
  }
}
