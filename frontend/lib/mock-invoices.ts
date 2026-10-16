import type { Invoice } from "./api";

// What the real backend returned for the two shipped samples, so mock mode
// shows a clean invoice and a receipt with a failed subtotal check.

export const MOCK_INVOICE: Invoice = {
  document_type: "invoice",
  vendor: {
    name: "Fernhill Paper Co.",
    address: "Unit 7, Tanner's Yard, Ashbury AB4 2QT, United Kingdom",
    tax_id: "GB 000 4417 21",
    email: "accounts@fernhill-paper.example",
  },
  customer: { name: "Quillon Design Studio", address: "22 Marlow Street, Ashbury AB1 6LD, United Kingdom", tax_id: null, email: null },
  invoice_number: "FPC-2026-0931",
  issue_date: "2026-09-30",
  due_date: "2026-10-30",
  currency: "GBP",
  line_items: [
    { description: "Recycled card stock A4, pack of 250", quantity: "10", unit_price: "18.50", amount: "185.00" },
    { description: "Kraft envelopes C5, box of 500", quantity: "4", unit_price: "32.00", amount: "128.00" },
    { description: "Letterpress business cards, set of 200", quantity: "2", unit_price: "64.75", amount: "129.50" },
    { description: "Next-day delivery", quantity: "1", unit_price: "12.00", amount: "12.00" },
  ],
  subtotal: "454.50",
  taxes: [{ label: "VAT", rate_percent: "20", amount: "90.90" }],
  discount: null,
  total: "545.40",
  checks: [
    { name: "line_amounts", status: "pass", expected: null, actual: null, detail: "All 4 line amounts match quantity × price." },
    { name: "subtotal", status: "pass", expected: "454.50", actual: "454.50", detail: "Lines add up to the subtotal." },
    { name: "total", status: "pass", expected: "545.40", actual: "545.40", detail: "Subtotal plus tax equals the total." },
    { name: "dates", status: "pass", expected: null, actual: null, detail: "The due date is on or after the issue date." },
    { name: "currency", status: "pass", expected: null, actual: null, detail: "GBP is a valid ISO 4217 currency code." },
  ],
};

export const MOCK_RECEIPT: Invoice = {
  document_type: "receipt",
  vendor: { name: "Copperleaf Cafe", address: "418 Orchard Ave, Millbrook OR", tax_id: null, email: null },
  customer: null,
  invoice_number: "4471",
  issue_date: "2026-10-03",
  due_date: null,
  currency: "USD",
  line_items: [
    { description: "Flat white", quantity: "2", unit_price: "4.20", amount: "8.40" },
    { description: "Almond croissant", quantity: "1", unit_price: "3.85", amount: "3.85" },
    { description: "Avocado toast", quantity: "1", unit_price: "9.50", amount: "9.50" },
    { description: "Sparkling water", quantity: "2", unit_price: "2.10", amount: "4.20" },
  ],
  subtotal: "26.95",
  taxes: [{ label: "Sales tax", rate_percent: "8", amount: "2.16" }],
  discount: null,
  total: "29.11",
  checks: [
    { name: "line_amounts", status: "pass", expected: null, actual: null, detail: "All 4 line amounts match quantity × price." },
    { name: "subtotal", status: "fail", expected: "25.95", actual: "26.95", detail: "Lines add up to 25.95 but the subtotal says 26.95." },
    { name: "total", status: "pass", expected: "29.11", actual: "29.11", detail: "Subtotal plus tax equals the total." },
    { name: "dates", status: "skipped", expected: null, actual: null, detail: "Needs both an issue date and a due date." },
    { name: "currency", status: "pass", expected: null, actual: null, detail: "USD is a valid ISO 4217 currency code." },
  ],
};
