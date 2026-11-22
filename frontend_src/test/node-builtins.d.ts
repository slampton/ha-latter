/**
 * Minimal ambient Node >= 24 built-in declarations for `frontend_src/test/**`
 * so `tsc --noEmit` validates both `src/` and `test/` with zero external `@types/node` dependency.
 */

declare module "node:test" {
  export type TestFn = () => void | Promise<void>;
  export function describe(name: string, fn: () => void): void;
  export function it(name: string, fn: TestFn): void;
  export function beforeEach(fn: TestFn): void;
  export function afterEach(fn: TestFn): void;
}

declare module "node:assert/strict" {
  function assert(value: unknown, message?: string | Error): asserts value;
  namespace assert {
    function ok(value: unknown, message?: string | Error): asserts value;
    function equal<T>(actual: unknown, expected: T, message?: string | Error): asserts actual is T;
    function notEqual(actual: unknown, expected: unknown, message?: string | Error): void;
    function strictEqual<T>(
      actual: unknown,
      expected: T,
      message?: string | Error,
    ): asserts actual is T;
    function notStrictEqual(actual: unknown, expected: unknown, message?: string | Error): void;
    function deepEqual<T>(
      actual: unknown,
      expected: T,
      message?: string | Error,
    ): asserts actual is T;
    function throws(block: () => unknown, error?: RegExp | Error, message?: string): void;
    function rejects(
      block: (() => Promise<unknown>) | Promise<unknown>,
      error?: RegExp | Error,
      message?: string,
    ): Promise<void>;
  }
  export default assert;
}

declare module "node:fs" {
  namespace fs {
    function readFileSync(path: string, encoding: "utf8" | "utf-8"): string;
    function existsSync(path: string): boolean;
  }
  export default fs;
  export const readFileSync: typeof fs.readFileSync;
  export const existsSync: typeof fs.existsSync;
}

declare module "node:path" {
  namespace path {
    function dirname(p: string): string;
    function resolve(...paths: string[]): string;
    function join(...paths: string[]): string;
  }
  export default path;
  export const dirname: typeof path.dirname;
  export const resolve: typeof path.resolve;
  export const join: typeof path.join;
}

declare module "node:url" {
  export function fileURLToPath(url: string | URL): string;
}
