import { describe, expect, it } from "vitest";
import { ApiError, createClient, type Transport, type TransportRequest, type TransportResponse } from "./api";

function clientReturning(res: TransportResponse | Error) {
  const requests: TransportRequest[] = [];
  const transport: Transport = async (req) => {
    requests.push(req);
    if (res instanceof Error) throw res;
    return res;
  };
  return { client: createClient(transport), requests };
}

async function caught(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (e) {
    expect(e).toBeInstanceOf(ApiError);
    return e as ApiError;
  }
  throw new Error("expected the call to reject");
}

const errorBody = (code: string, message: string) => JSON.stringify({ error: { code, message } });

describe("api client errors", () => {
  it("surfaces the backend's code and message verbatim", async () => {
    const { client } = clientReturning({
      status: 413,
      retryAfter: null,
      text: errorBody("file_too_large", "PDFs must be 10 MB or smaller."),
    });
    const err = await caught(client.uploadDocument("s_1", new File(["%PDF"], "a.pdf")));
    expect(err).toMatchObject({ status: 413, code: "file_too_large", message: "PDFs must be 10 MB or smaller." });
  });

  it("reads Retry-After seconds on a 429", async () => {
    const { client } = clientReturning({
      status: 429,
      retryAfter: "42",
      text: errorBody("rate_limited", "Slow down a little."),
    });
    const err = await caught(client.ask("s_1", "hi"));
    expect(err).toMatchObject({ code: "rate_limited", message: "Slow down a little.", retryAfter: 42 });
  });

  it("ignores Retry-After on statuses other than 429", async () => {
    const { client } = clientReturning({ status: 503, retryAfter: "10", text: errorBody("llm_quota", "Quota used.") });
    const err = await caught(client.ask("s_1", "hi"));
    expect(err.retryAfter).toBeNull();
  });

  it("maps session_not_found so callers can branch on it", async () => {
    const { client } = clientReturning({
      status: 404,
      retryAfter: null,
      text: errorBody("session_not_found", "That session expired."),
    });
    const err = await caught(client.listDocuments("s_gone"));
    expect(err.code).toBe("session_not_found");
  });

  it("falls back to a generic message when the body is not the error shape", async () => {
    const { client } = clientReturning({ status: 502, retryAfter: null, text: "<html>Bad gateway</html>" });
    const err = await caught(client.config());
    expect(err).toMatchObject({ status: 502, code: "unknown" });
    expect(err.message).toContain("502");
  });

  it("reports a network failure as code network", async () => {
    const { client } = clientReturning(new Error("offline"));
    const err = await caught(client.health());
    expect(err).toMatchObject({ status: 0, code: "network" });
  });
});

describe("api client success", () => {
  it("returns parsed bodies and resolves 204 with no body", async () => {
    const ok = clientReturning({ status: 201, retryAfter: null, text: JSON.stringify({ session_id: "s_8f3k" }) });
    await expect(ok.client.createSession()).resolves.toBe("s_8f3k");

    const empty = clientReturning({ status: 204, retryAfter: null, text: "" });
    await expect(empty.client.deleteDocument("s_1", "d_1")).resolves.toBeUndefined();
    expect(empty.requests[0]).toMatchObject({ method: "DELETE", path: "/api/sessions/s_1/documents/d_1" });
  });

  it("sends the question as JSON and nothing else", async () => {
    const { client, requests } = clientReturning({
      status: 200,
      retryAfter: null,
      text: JSON.stringify({ answer: "No.", citations: [] }),
    });
    await client.ask("s_1", "Is there a fee?");
    expect(requests[0]).toMatchObject({ method: "POST", path: "/api/sessions/s_1/ask", json: { question: "Is there a fee?" } });
  });

  it("posts the contract as the multipart file field", async () => {
    const { client, requests } = clientReturning({
      status: 200,
      retryAfter: null,
      text: JSON.stringify({ document_name: "lease.pdf", pages: 3, review: {} }),
    });
    const file = new File(["%PDF"], "lease.pdf");
    await expect(client.reviewContract(file)).resolves.toMatchObject({ document_name: "lease.pdf", pages: 3 });
    expect(requests[0]).toMatchObject({ method: "POST", path: "/api/contracts/review" });
    expect(requests[0].form?.get("file")).toBe(file);
  });
});
