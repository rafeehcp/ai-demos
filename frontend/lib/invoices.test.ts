import { describe, expect, it } from "vitest";
import type { Config, ExtractResponse, Invoice } from "./api";
import { batchReducer, buildCsv, buildJson, csvField, formatAmount, rejectReason, type Card } from "./invoices";

const invoice = (overrides: Partial<Invoice> = {}): Invoice => ({
  document_type: "invoice",
  vendor: { name: "Fernhill Paper Co.", address: "Unit 7, Tanner's Yard, Ashbury", tax_id: null, email: null },
  customer: null,
  invoice_number: "FPC-1",
  issue_date: "2026-09-30",
  due_date: null,
  currency: "GBP",
  line_items: [
    { description: "Card stock", quantity: "10", unit_price: "18.50", amount: "185.00" },
    { description: "Delivery", quantity: null, unit_price: null, amount: "12.00" },
  ],
  subtotal: "197.00",
  taxes: [
    { label: "CGST", rate_percent: "9", amount: "17.73" },
    { label: "SGST", rate_percent: null, amount: "17.73" },
  ],
  discount: null,
  total: "232.46",
  checks: [
    { name: "subtotal", status: "fail", expected: "197.00", actual: "179.00", detail: "x" },
    { name: "total", status: "pass", expected: null, actual: null, detail: "y" },
    { name: "dates", status: "fail", expected: null, actual: null, detail: "z" },
  ],
  ...overrides,
});

const parseRows = (csv: string) => csv.split("\r\n").slice(0, -1);

describe("buildCsv", () => {
  it("writes a header and one row per line item with the invoice fields repeated", () => {
    const rows = parseRows(buildCsv([{ file_name: "a.pdf", invoice: invoice() }]));
    expect(rows).toHaveLength(3);
    expect(rows[0].split(",")).toContain("line_description");
    expect(rows[1]).toBe(
      'a.pdf,invoice,Fernhill Paper Co.,"Unit 7, Tanner\'s Yard, Ashbury",,,,,,,FPC-1,2026-09-30,,GBP,197.00,,CGST 9%: 17.73; SGST: 17.73,232.46,subtotal; dates,1,Card stock,10,18.50,185.00',
    );
    expect(rows[2]).toBe(
      'a.pdf,invoice,Fernhill Paper Co.,"Unit 7, Tanner\'s Yard, Ashbury",,,,,,,FPC-1,2026-09-30,,GBP,197.00,,CGST 9%: 17.73; SGST: 17.73,232.46,subtotal; dates,2,Delivery,,,12.00',
    );
  });

  it("gives an invoice with no line items one row with empty line columns", () => {
    const rows = parseRows(buildCsv([{ file_name: "empty.jpg", invoice: invoice({ line_items: [] }) }]));
    expect(rows).toHaveLength(2);
    expect(rows[1].endsWith("subtotal; dates,,,,,")).toBe(true);
  });

  it("keeps rows from several files in order", () => {
    const results: ExtractResponse[] = [
      { file_name: "one.pdf", invoice: invoice() },
      { file_name: "two.png", invoice: invoice({ line_items: [] }) },
    ];
    expect(parseRows(buildCsv(results)).map((r) => r.split(",")[0])).toEqual(["file_name", "one.pdf", "one.pdf", "two.png"]);
  });

  it("ends every record with CRLF", () => {
    const csv = buildCsv([{ file_name: "a.pdf", invoice: invoice() }]);
    expect(csv.endsWith("\r\n")).toBe(true);
    expect(csv.replace(/\r\n/g, "")).not.toMatch(/[\r\n]/);
  });
});

describe("csvField", () => {
  it.each([
    ["plain", "plain"],
    ["a, b", '"a, b"'],
    ['say "hi"', '"say ""hi"""'],
    ["two\nlines", '"two\nlines"'],
    ["cr\rhere", '"cr\rhere"'],
    [null, ""],
    [3, "3"],
    ["-10.00", "-10.00"],
    ['=HYPERLINK("http://x")', `"'=HYPERLINK(""http://x"")"`],
    ["+1 555 0100", "'+1 555 0100"],
    ["@SUM(A1)", "'@SUM(A1)"],
    ["-discount", "'-discount"],
  ])("quotes %j as %j", (value, expected) => {
    expect(csvField(value)).toBe(expected);
  });

  it("keeps a quoted newline inside one record", () => {
    const csv = buildCsv([
      { file_name: "a.pdf", invoice: invoice({ line_items: [{ description: 'Line "one"\nsecond, line', quantity: null, unit_price: null, amount: "1.00" }] }) },
    ]);
    expect(csv).toContain(',"Line ""one""\nsecond, line",,,1.00\r\n');
  });
});

describe("buildJson", () => {
  it("is an array of results with money as strings", () => {
    const parsed = JSON.parse(buildJson([{ file_name: "a.pdf", invoice: invoice() }]));
    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed[0].invoice.total).toBe("232.46");
  });
});

describe("formatAmount", () => {
  it.each([
    ["1324.26", "1,324.26"],
    ["999.5", "999.5"],
    ["1000", "1,000"],
    ["-131.38", "-131.38"],
    ["1234567.891", "1,234,567.891"],
    ["0.30000000000000004", "0.30000000000000004"],
    ["n/a", "n/a"],
  ])("%s -> %s", (value, expected) => {
    expect(formatAmount(value)).toBe(expected);
  });
});

const config: Config = {
  max_documents: 3,
  max_file_mb: 1,
  max_pages: 100,
  contract_max_pages: 40,
  invoice_max_files: 5,
  invoice_max_pages: 5,
  provider_label: "Test",
};

describe("rejectReason", () => {
  const file = (name: string, type: string, size = 10) => new File([new Uint8Array(size)], name, { type });

  it("accepts PDFs and PNG, JPEG and WebP images", () => {
    for (const [name, type] of [["a.pdf", "application/pdf"], ["b.png", "image/png"], ["c.JPG", ""], ["d.webp", "image/webp"]]) {
      expect(rejectReason(file(name, type), null, config)).toBeNull();
    }
  });

  it("refuses other types, files over the size limit and PDFs over the page limit", () => {
    expect(rejectReason(file("a.gif", "image/gif"), null, config)).toMatch(/PDF, PNG, JPEG and WebP/);
    expect(rejectReason(file("a.pdf", "application/pdf", 1024 * 1024 + 1), null, config)).toBe("Files must be 1 MB or smaller.");
    expect(rejectReason(file("a.pdf", "application/pdf"), 6, config)).toBe("PDFs must have 5 pages or fewer.");
    expect(rejectReason(file("a.pdf", "application/pdf"), 5, config)).toBeNull();
  });
});

describe("batchReducer", () => {
  const card = (id: string): Card => ({ id, name: `${id}.pdf`, kind: "pdf", url: `blob:${id}`, status: { state: "queued" } });
  const result: ExtractResponse = { file_name: "a.pdf", invoice: invoice() };

  it("moves a card through extracting to done or failed, and back to queued on retry", () => {
    let cards = batchReducer([], { type: "add", cards: [card("a"), card("b")] });
    cards = batchReducer(cards, { type: "start", id: "a" });
    expect(cards.map((c) => c.status.state)).toEqual(["extracting", "queued"]);
    cards = batchReducer(cards, { type: "done", id: "a", result });
    cards = batchReducer(cards, { type: "failed", id: "b", message: "busy" });
    expect(cards[1].status).toEqual({ state: "failed", message: "busy", retryable: true });
    cards = batchReducer(cards, { type: "retry", id: "b" });
    expect(cards.map((c) => c.status.state)).toEqual(["done", "queued"]);
  });

  it("drops a result that arrives after the batch was cleared", () => {
    const cleared = batchReducer([card("a")], { type: "clear" });
    expect(batchReducer(cleared, { type: "done", id: "a", result })).toEqual([]);
  });
});
