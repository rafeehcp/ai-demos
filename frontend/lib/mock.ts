// In-memory stand-in for the backend, used when NEXT_PUBLIC_API_URL is unset
// in dev or set to "mock". It speaks the docs/api.md contract at the Transport
// level, so the real client's parsing and error handling still run.
//
// Questions starting with these commands trigger contract errors:
//   !429      rate_limited with Retry-After: 30
//   !expire   drops the session, then session_not_found
//   !quota    llm_quota
//   !none     an answer with no citations
//
// A contract review returns MOCK_REVIEW. An invoice extraction returns
// MOCK_RECEIPT for images and MOCK_INVOICE for PDFs. Upload a file named
// error.pdf to get llm_error from either.

import type {
  AskResponse,
  Citation,
  Config,
  DocumentInfo,
  ExtractResponse,
  ReviewResponse,
  Transport,
  TransportResponse,
} from "./api";
import { fileKind } from "./invoices";
import { MOCK_INVOICE, MOCK_RECEIPT } from "./mock-invoices";
import { MOCK_REVIEW } from "./mock-review";
import { countPdfPages } from "./pdf";

const config: Config = {
  max_documents: 3,
  max_file_mb: 10,
  max_pages: 100,
  contract_max_pages: 40,
  invoice_max_files: 5,
  invoice_max_pages: 5,
  provider_label: "Mock provider",
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const id = (prefix: string) => `${prefix}_${Math.random().toString(36).slice(2, 8)}`;

const json = (status: number, body: unknown, retryAfter: string | null = null): TransportResponse => ({
  status,
  retryAfter,
  text: body === undefined ? "" : JSON.stringify(body),
});
const fail = (status: number, code: string, message: string, retryAfter: string | null = null) =>
  json(status, { error: { code, message } }, retryAfter);

function answerFor(question: string, docs: DocumentInfo[]): AskResponse {
  if (question.startsWith("!none")) {
    return { answer: "The uploaded documents don't say anything about that.", citations: [] };
  }
  const first = docs[0];
  const second = docs[1] ?? first;
  const citations: Citation[] = [
    {
      n: 1,
      document_id: first.id,
      document_name: first.name,
      page: Math.min(2, first.pages),
      quote: `…a mock excerpt from page ${Math.min(2, first.pages)} of ${first.name}. The real backend returns up to 300 characters of the retrieved chunk here…`,
    },
    {
      n: 2,
      document_id: second.id,
      document_name: second.name,
      page: second.pages,
      quote: `…another mock excerpt, this time from the last page of ${second.name}…`,
    },
  ];
  return {
    answer:
      `This is a mock answer to "${question}". The most relevant passage is on page ${citations[0].page} of ${first.name} [1]. ` +
      `A second passage supports it [2]. Markers the server never cited, like [7], stay as plain text.`,
    citations,
  };
}

export function mockTransport(): Transport {
  const sessions = new Map<string, DocumentInfo[]>();
  let awake = false;

  return async (req) => {
    const { method, path } = req;

    if (method === "GET" && path === "/api/health") {
      if (!awake) {
        await sleep(2500);
        awake = true;
      }
      return json(200, { status: "ok" });
    }
    if (method === "GET" && path === "/api/config") return json(200, config);
    if (method === "POST" && path === "/api/sessions") {
      const sessionId = id("s");
      sessions.set(sessionId, []);
      return json(201, { session_id: sessionId });
    }

    if (method === "POST" && path === "/api/invoices/extract") {
      const file = req.form?.get("file");
      const kind = file instanceof File ? fileKind(file) : null;
      if (!(file instanceof File) || kind === null) {
        return fail(400, "unsupported_file", "That file type isn't supported. Upload a PDF, PNG, JPEG or WebP file.");
      }
      await sleep(2500);
      if (file.name.toLowerCase() === "error.pdf") {
        return fail(502, "llm_error", "The AI model returned a reply the app couldn't read. Please try again.");
      }
      const response: ExtractResponse = { file_name: file.name, invoice: kind === "image" ? MOCK_RECEIPT : MOCK_INVOICE };
      return json(200, response);
    }

    if (method === "POST" && path === "/api/contracts/review") {
      const file = req.form?.get("file");
      if (!(file instanceof File) || !file.name.toLowerCase().endsWith(".pdf")) {
        return fail(400, "not_a_pdf", "That file isn't a PDF. Please upload a .pdf file.");
      }
      for (let i = 1; i <= 10; i++) {
        await sleep(40);
        req.onUploadProgress?.(i / 10);
      }
      await sleep(4000);
      if (file.name.toLowerCase() === "error.pdf") {
        return fail(502, "llm_error", "The AI model returned a review the app couldn't read. Please try again.");
      }
      const response: ReviewResponse = {
        document_name: file.name,
        pages: (await countPdfPages(file)) ?? 1,
        review: MOCK_REVIEW,
      };
      return json(200, response);
    }

    const m = path.match(/^\/api\/sessions\/([^/]+)\/(documents|ask)(?:\/([^/]+))?$/);
    if (!m) return fail(404, "not_found", `Mock has no route for ${method} ${path}.`);
    const [, sessionId, resource, documentId] = m;
    const docs = sessions.get(decodeURIComponent(sessionId));
    if (!docs) return fail(404, "session_not_found", "Your session expired. Upload your documents again.");

    if (resource === "documents" && method === "GET") return json(200, { documents: docs });

    if (resource === "documents" && method === "POST") {
      const file = req.form?.get("file");
      if (!(file instanceof File) || !file.name.toLowerCase().endsWith(".pdf")) {
        return fail(400, "not_a_pdf", "That file isn't a PDF.");
      }
      if (docs.length >= config.max_documents) {
        return fail(409, "too_many_documents", `You can upload up to ${config.max_documents} documents.`);
      }
      if (file.size > config.max_file_mb * 1024 * 1024) {
        return fail(413, "file_too_large", `PDFs must be ${config.max_file_mb} MB or smaller.`);
      }
      for (let i = 1; i <= 10; i++) {
        await sleep(60);
        req.onUploadProgress?.(i / 10);
      }
      await sleep(1200);
      const pages = (await countPdfPages(file)) ?? 1;
      const doc: DocumentInfo = { id: id("d"), name: file.name, pages, chunks: pages * 3 };
      docs.push(doc);
      return json(201, doc);
    }

    if (resource === "documents" && method === "DELETE" && documentId) {
      const i = docs.findIndex((d) => d.id === decodeURIComponent(documentId));
      if (i >= 0) docs.splice(i, 1);
      return json(204, undefined);
    }

    if (resource === "ask" && method === "POST") {
      await sleep(900);
      const question = String((req.json as { question?: unknown })?.question ?? "").trim();
      if (!question || question.length > 1000) {
        return fail(400, "empty_question", "Type a question of up to 1,000 characters.");
      }
      if (question.startsWith("!429")) {
        return fail(429, "rate_limited", "You're sending requests too quickly.", "30");
      }
      if (question.startsWith("!quota")) {
        return fail(503, "llm_quota", "The demo's free AI quota is used up for now. Try again later.");
      }
      if (question.startsWith("!expire")) {
        sessions.delete(decodeURIComponent(sessionId));
        return fail(404, "session_not_found", "Your session expired. Upload your documents again.");
      }
      if (docs.length === 0) return fail(409, "no_documents", "Upload a document before asking a question.");
      return json(200, answerFor(question, docs));
    }

    return fail(405, "method_not_allowed", `Mock has no route for ${method} ${path}.`);
  };
}
