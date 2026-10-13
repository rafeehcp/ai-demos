import { ApiError, type ApiClient } from "./api";

/** The part of a demo's server state that ServerStatus renders. */
export type BootPhase =
  | { phase: "waking"; slow: boolean }
  | { phase: "ready" }
  | { phase: "failed"; message: string }
  | { phase: "unconfigured" };

/** Show "Waking up the server" instead of "Connecting" after this long. */
export const SLOW_AFTER_MS = 1_500;
const WAKE_DEADLINE_MS = 120_000;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Resolves once /api/health answers. A sleeping free-tier host can drop or
 * stall the first requests, so this keeps knocking until the deadline.
 * Resolves false if the caller cancelled while waiting.
 */
export async function waitForServer(client: ApiClient, cancelled: () => boolean): Promise<boolean> {
  const deadline = Date.now() + WAKE_DEADLINE_MS;
  for (;;) {
    try {
      await client.health(60_000);
      return !cancelled();
    } catch (err) {
      if (cancelled()) return false;
      if (Date.now() > deadline) throw err;
      await sleep(3_000);
    }
  }
}

export function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "rate_limited" && err.retryAfter !== null) {
      const s = err.retryAfter;
      return `${err.message} Try again in ${s} second${s === 1 ? "" : "s"}.`;
    }
    return err.message;
  }
  return "Something went wrong in the page. Reload it and try again.";
}
