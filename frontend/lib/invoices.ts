import type { Check, CheckName, Config, ExtractResponse, Invoice } from "./api";

export type FileKind = "pdf" | "image";

export type CardStatus =
  | { state: "queued" }
  | { state: "extracting" }
  | { state: "done"; result: ExtractResponse }
  /** `retryable` is false when the file itself was refused before sending. */
  | { state: "failed"; message: string; retryable: boolean };

/** `kind` is null for a file type the app refused. */
export type Card = { id: string; name: string; kind: FileKind | null; url: string; status: CardStatus };

export type BatchAction =
  | { type: "add"; cards: Card[] }
  | { type: "start"; id: string }
  | { type: "done"; id: string; result: ExtractResponse }
  | { type: "failed"; id: string; message: string }
  | { type: "retry"; id: string }
  | { type: "clear" };

/** Results for a card that was cleared mid-request are dropped: no card has that id any more. */
export function batchReducer(cards: Card[], action: BatchAction): Card[] {
  const update = (id: string, status: CardStatus) => cards.map((c) => (c.id === id ? { ...c, status } : c));
  switch (action.type) {
    case "add":
      return [...cards, ...action.cards];
    case "start":
      return update(action.id, { state: "extracting" });
    case "done":
      return update(action.id, { state: "done", result: action.result });
    case "failed":
      return update(action.id, { state: "failed", message: action.message, retryable: true });
    case "retry":
      return update(action.id, { state: "queued" });
    case "clear":
      return [];
  }
}

const IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const IMAGE_EXTENSIONS = /\.(png|jpe?g|webp)$/i;

export function fileKind(file: File): FileKind | null {
  if (file.type === "application/pdf" || /\.pdf$/i.test(file.name)) return "pdf";
  if (IMAGE_TYPES.has(file.type) || IMAGE_EXTENSIONS.test(file.name)) return "image";
  return null;
}

/** Why the file can't be sent, or null. `pages` is null when the count couldn't be read. */
export function rejectReason(file: File, pages: number | null, config: Config): string | null {
  if (fileKind(file) === null) return "Only PDF, PNG, JPEG and WebP files are supported.";
  if (file.size > config.max_file_mb * 1024 * 1024) return `Files must be ${config.max_file_mb} MB or smaller.`;
  if (pages !== null && pages > config.invoice_max_pages) {
    return `PDFs must have ${config.invoice_max_pages} pages or fewer.`;
  }
  return null;
}

export const CHECK_LABELS: Record<CheckName, string> = {
  line_amounts: "Line amounts",
  subtotal: "Subtotal",
  total: "Total",
  dates: "Dates",
  currency: "Currency",
};

export const STATUS_LABELS: Record<Check["status"], string> = {
  pass: "Passed",
  fail: "Failed",
  skipped: "Skipped",
};

export const DOCUMENT_LABELS: Record<Invoice["document_type"], string> = {
  invoice: "Invoice",
  receipt: "Receipt",
  credit_note: "Credit note",
  other: "Document",
};

/**
 * "1324.26" -> "1,324.26". Works on the decimal string so no value passes
 * through a float. Returns anything that isn't a plain number unchanged.
 */
export function formatAmount(value: string): string {
  const match = /^(-?)(\d+)(\.\d+)?$/.exec(value);
  if (!match) return value;
  const [, sign, whole, fraction = ""] = match;
  return sign + whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + fraction;
}

export function formatMoney(value: string, currency: string | null): string {
  return currency ? `${currency} ${formatAmount(value)}` : formatAmount(value);
}

export function countFailed(invoice: Invoice): number {
  return invoice.checks.filter((c) => c.status === "fail").length;
}

const CSV_COLUMNS = [
  "file_name",
  "document_type",
  "vendor_name",
  "vendor_address",
  "vendor_tax_id",
  "vendor_email",
  "customer_name",
  "customer_address",
  "customer_tax_id",
  "customer_email",
  "invoice_number",
  "issue_date",
  "due_date",
  "currency",
  "subtotal",
  "discount",
  "taxes",
  "total",
  "failed_checks",
  "line_number",
  "line_description",
  "line_quantity",
  "line_unit_price",
  "line_amount",
] as const;

type CsvRow = Record<(typeof CSV_COLUMNS)[number], string | number | null>;

const PLAIN_NUMBER = /^-?\d+(\.\d+)?$/;

export function csvField(value: string | number | null): string {
  let text = value === null ? "" : String(value);
  // Text read from an uploaded document must not run as a spreadsheet formula when the CSV is opened.
  if (/^[=+\-@\t\r]/.test(text) && !PLAIN_NUMBER.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** RFC 4180: CRLF line ends, a header row, and one row per line item with the invoice fields repeated. */
export function buildCsv(results: ExtractResponse[]): string {
  const rows = results.flatMap(({ file_name, invoice: inv }): CsvRow[] => {
    const base = {
      file_name,
      document_type: inv.document_type,
      vendor_name: inv.vendor?.name ?? null,
      vendor_address: inv.vendor?.address ?? null,
      vendor_tax_id: inv.vendor?.tax_id ?? null,
      vendor_email: inv.vendor?.email ?? null,
      customer_name: inv.customer?.name ?? null,
      customer_address: inv.customer?.address ?? null,
      customer_tax_id: inv.customer?.tax_id ?? null,
      customer_email: inv.customer?.email ?? null,
      invoice_number: inv.invoice_number,
      issue_date: inv.issue_date,
      due_date: inv.due_date,
      currency: inv.currency,
      subtotal: inv.subtotal,
      discount: inv.discount,
      taxes: inv.taxes.map((t) => `${t.label}${t.rate_percent ? ` ${t.rate_percent}%` : ""}: ${t.amount}`).join("; "),
      total: inv.total,
      failed_checks: inv.checks.filter((c) => c.status === "fail").map((c) => c.name).join("; "),
    };
    const noLine = { line_number: null, line_description: null, line_quantity: null, line_unit_price: null, line_amount: null };
    if (inv.line_items.length === 0) return [{ ...base, ...noLine }];
    return inv.line_items.map((line, i) => ({
      ...base,
      line_number: i + 1,
      line_description: line.description,
      line_quantity: line.quantity,
      line_unit_price: line.unit_price,
      line_amount: line.amount,
    }));
  });
  const lines = [CSV_COLUMNS.join(","), ...rows.map((row) => CSV_COLUMNS.map((col) => csvField(row[col])).join(","))];
  return lines.join("\r\n") + "\r\n";
}

export function buildJson(results: ExtractResponse[]): string {
  return JSON.stringify(results, null, 2) + "\n";
}
