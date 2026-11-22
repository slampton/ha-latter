/**
 * Minimal ambient Node >= 24 built-in declarations for `frontend_src/test/**`,
 * `frontend_src/e2e/**`, and `playwright.config.ts` so `tsc --noEmit` validates
 * the entire Studio test & E2E surface with zero `@types/node` dependency.
 */

interface Buffer extends Uint8Array {
  toString(encoding?: "utf8" | "utf-8" | "base64" | "hex" | string): string;
}

declare var Buffer: {
  from(
    input: string | ArrayLike<number> | ArrayBufferLike,
    encoding?: "utf8" | "utf-8" | "base64" | "hex" | string,
  ): Buffer;
  isBuffer(obj: unknown): obj is Buffer;
};

declare var process: {
  readonly env: Readonly<Record<string, string | undefined>>;
  cwd(): string;
};

declare module "child_process" {
  export interface ChildProcess {
    readonly pid?: number;
  }
}

declare module "stream" {
  export interface Readable {
    readonly readable?: boolean;
  }
}

declare module "fs" {
  export interface ReadStream {
    readonly path?: string | Buffer;
  }
}

declare module "node:test" {
  export type TestFn = () => void | Promise<void>;
  export function describe(name: string, fn: () => void): void;
  export function it(name: string, fn: TestFn): void;
  export function before(fn: TestFn): void;
  export function after(fn: TestFn): void;
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
    function match(value: string, regExp: RegExp, message?: string | Error): void;
    function doesNotMatch(value: string, regExp: RegExp, message?: string | Error): void;
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
    function readFileSync(path: string): Buffer;
    function existsSync(path: string): boolean;
    function unlinkSync(path: string): void;
  }
  export default fs;
  export const readFileSync: typeof fs.readFileSync;
  export const existsSync: typeof fs.existsSync;
  export const unlinkSync: typeof fs.unlinkSync;
}

declare module "node:os" {
  namespace os {
    function tmpdir(): string;
  }
  export default os;
  export const tmpdir: typeof os.tmpdir;
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
