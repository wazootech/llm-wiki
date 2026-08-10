import type { WikiCommandResult } from "./types";

/** Thrown when a wiki CLI command exits with a non-zero status code. */
export class WikiCommandError extends Error {
  /** The full result object from the failed command. */
  readonly result: WikiCommandResult;

  constructor(result: WikiCommandResult) {
    const detail =
      result.stderr.trim() ||
      result.stdout.trim() ||
      `exit code ${result.exitCode}`;
    super(`wiki command failed: ${detail}`);
    this.name = "WikiCommandError";
    this.result = result;
  }
}

/** Thrown when the wazootech-wiki Python virtualenv cannot be set up or found. */
export class WikiSetupError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WikiSetupError";
  }
}
