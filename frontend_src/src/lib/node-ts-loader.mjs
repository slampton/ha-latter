/**
 * Minimal Node 24+ synchronous `registerHooks` helper for `node --test` so TypeScript
 * modules using standard ESM `.js` relative specifiers resolve `.ts` siblings directly.
 */

import fs from "node:fs";
import { registerHooks } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (
      specifier.startsWith(".") &&
      specifier.endsWith(".js") &&
      context.parentURL?.startsWith("file:")
    ) {
      const parentDir = path.dirname(fileURLToPath(context.parentURL));
      const jsPath = path.resolve(parentDir, specifier);
      if (!fs.existsSync(jsPath)) {
        const tsPath = `${jsPath.slice(0, -3)}.ts`;
        if (fs.existsSync(tsPath)) {
          return nextResolve(pathToFileURL(tsPath).href, context);
        }
      }
    }
    return nextResolve(specifier, context);
  },
});
