// Typed client for docs/api.md. Every call goes through one Transport, so the
// browser (XHR), the dev mock and the unit tests share the same parsing and
// error handling.

export type Config = {
  max_documents: number;
  max_file_mb: number;
  max_pages: number;
  provider_label: string;
};

export type DocumentInfo = {
  id: string;
  name: string;
  pages: number;
  chunks: number;
};

export type Citation = {
  n: number;
  document_id: string;
  document_name: string;
  page: number;
  quote: string;
};

export type AskResponse = {
  answer: string;
  citations: Citation[];
};

export type ErrorCode =
  | "not_a_pdf"
  | "no_text"
  | "empty_question"
  | "session_not_found"
  | "too_many_documents"
  | "no_documents"
  | "file_too_large"
  | "rate_limited"
  | "llm_error"
  | "llm_quota"
  // Client-side codes: the server never sends these.
  | "network"
  | "unknown";

export class ApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  /** Seconds to wait, from Retry-After on a 429. */
  readonly retryAfter: number | null;

  constructor(status: number, code: ErrorCode, message: string, retryAfter: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

export type TransportRequest = {
  method: "GET" | "POST" | "DELETE";
  path: string;
  json?: unknown;
  form?: FormData;
  /** Upload progress as a fraction from 0 to 1. */
  onUploadProgress?: (fraction: number) => void;
  timeoutMs?: number;
};

export type TransportResponse = {
  status: number;
  retryAfter: string | null;
  /** Raw response text; empty for 204. */
  text: string;
};

/** Resolves for any HTTP status. Rejects only when no response arrived. */
export type Transport = (req: TransportRequest) => Promise<TransportResponse>;

export function xhrTransport(baseUrl: string): Transport {
  const base = baseUrl.replace(/\/+$/, "");
  return (req) =>
    new Promise((resolve, reject) => {
      // XHR rather than fetch: fetch cannot report upload progress.
      const xhr = new XMLHttpRequest();
      xhr.open(req.method, base + req.path);
      xhr.timeout = req.timeoutMs ?? 0;
      if (req.onUploadProgress) {
        const report = req.onUploadProgress;
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) report(e.loaded / e.total);
        };
      }
      xhr.onload = () =>
        resolve({
          status: xhr.status,
          retryAfter: xhr.getResponseHeader("Retry-After"),
          text: xhr.responseText,
        });
      xhr.onerror = () => reject(new Error("network error"));
      xhr.ontimeout = () => reject(new Error("timeout"));
      if (req.form) {
        xhr.send(req.form);
      } else if (req.json !== undefined) {
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(JSON.stringify(req.json));
      } else {
        xhr.send();
      }
    });
}

const KNOWN_CODES: ReadonlySet<string> = new Set<ErrorCode>([
  "not_a_pdf",
  "no_text",
  "empty_question",
  "session_not_found",
  "too_many_documents",
  "no_documents",
  "file_too_large",
  "rate_limited",
  "llm_error",
  "llm_quota",
]);

function parseRetryAfter(header: string | null): number | null {
  if (header === null) return null;
  const seconds = Number(header.trim());
  if (Number.isFinite(seconds) && seconds >= 0) return Math.ceil(seconds);
  const date = Date.parse(header);
  if (Number.isNaN(date)) return null;
  return Math.max(0, Math.ceil((date - Date.now()) / 1000));
}

function toApiError(res: TransportResponse): ApiError {
  const retryAfter = res.status === 429 ? parseRetryAfter(res.retryAfter) : null;
  let body: unknown;
  try {
    body = JSON.parse(res.text);
  } catch {
    body = null;
  }
  const error = (body as { error?: { code?: unknown; message?: unknown } } | null)?.error;
  if (error && typeof error.message === "string" && error.message.trim() !== "") {
    const code = typeof error.code === "string" && KNOWN_CODES.has(error.code) ? (error.code as ErrorCode) : "unknown";
    return new ApiError(res.status, code, error.message, retryAfter);
  }
  // Proxies and cold-starting hosts answer with HTML or nothing.
  if (res.status === 429) {
    return new ApiError(429, "rate_limited", "Too many requests.", retryAfter);
  }
  return new ApiError(res.status, "unknown", `The server returned an unexpected error (HTTP ${res.status}).`);
}

export type ApiClient = ReturnType<typeof createClient>;

export function createClient(transport: Transport) {
  async function call<T>(req: TransportRequest): Promise<T> {
    let res: TransportResponse;
    try {
      res = await transport(req);
    } catch {
      throw new ApiError(0, "network", "Can't reach the server. Check your connection and try again.");
    }
    if (res.status < 200 || res.status >= 300) throw toApiError(res);
    if (res.text === "") return undefined as T;
    try {
      return JSON.parse(res.text) as T;
    } catch {
      throw new ApiError(res.status, "unknown", "The server sent a response the app couldn't read.");
    }
  }

  const docsPath = (sessionId: string) => `/api/sessions/${encodeURIComponent(sessionId)}/documents`;

  return {
    health: (timeoutMs?: number) => call<{ status: "ok" }>({ method: "GET", path: "/api/health", timeoutMs }),

    config: () => call<Config>({ method: "GET", path: "/api/config" }),

    createSession: async () =>
      (await call<{ session_id: string }>({ method: "POST", path: "/api/sessions" })).session_id,

    uploadDocument: (sessionId: string, file: File, onUploadProgress?: (fraction: number) => void) => {
      const form = new FormData();
      form.append("file", file);
      return call<DocumentInfo>({ method: "POST", path: docsPath(sessionId), form, onUploadProgress });
    },

    listDocuments: async (sessionId: string) =>
      (await call<{ documents: DocumentInfo[] }>({ method: "GET", path: docsPath(sessionId) })).documents,

    deleteDocument: (sessionId: string, documentId: string) =>
      call<void>({ method: "DELETE", path: `${docsPath(sessionId)}/${encodeURIComponent(documentId)}` }),

    ask: (sessionId: string, question: string) =>
      call<AskResponse>({
        method: "POST",
        path: `/api/sessions/${encodeURIComponent(sessionId)}/ask`,
        json: { question },
      }),
  };
}
