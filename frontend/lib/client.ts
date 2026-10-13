import { createClient, xhrTransport, type ApiClient } from "./api";
import { mockTransport } from "./mock";

export type ClientSetup = { kind: "live" | "mock"; client: ApiClient } | { kind: "unconfigured" };

// Read once: Next inlines NEXT_PUBLIC_* at build time, but only for direct
// property access, so this must stay `process.env.NEXT_PUBLIC_API_URL`.
const apiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();

export function setupClient(): ClientSetup {
  if (apiUrl === "mock" || (!apiUrl && process.env.NODE_ENV === "development")) {
    return { kind: "mock", client: createClient(mockTransport()) };
  }
  if (!apiUrl) return { kind: "unconfigured" };
  return { kind: "live", client: createClient(xhrTransport(apiUrl)) };
}
