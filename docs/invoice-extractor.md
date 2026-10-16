# Demo 3: Invoice → JSON

A visitor uploads invoices or receipts (PDF or photo) and gets clean structured data: vendor, customer, dates, currency, line items, tax and totals, ready to download as JSON or CSV. The selling point is that **the numbers are checked**. The app does the arithmetic itself and shows which totals add up, so a misread digit is flagged instead of slipping into someone's books.

## Scope

- Up to `INVOICE_MAX_FILES` files per batch (default 5), each a PDF of at most `INVOICE_MAX_PAGES` pages (default 5) or a PNG/JPEG/WebP image, at most `MAX_FILE_MB`.
- Each file is extracted independently. The frontend sends files one at a time, so one bad file doesn't sink the batch, and the free backend never holds more than one file in memory.
- Stateless. Nothing is kept on the server after the response.

## Data shape

```text
Invoice
├─ document_type: "invoice" | "receipt" | "credit_note" | "other"
├─ vendor:   Party | null           Party = (name, address?, tax_id?, email?)
├─ customer: Party | null
├─ invoice_number: str | null
├─ issue_date: date | null          ISO 8601
├─ due_date:   date | null
├─ currency: str | null             ISO 4217, for example "USD"
├─ line_items: list[LineItem]       LineItem = (description, quantity?, unit_price?, amount)
├─ subtotal: Decimal | null
├─ taxes: list[Tax]                 Tax = (label, rate_percent?, amount)
├─ discount: Decimal | null
├─ total: Decimal | null
└─ checks: list[Check]              computed by the backend, never by the model

Check = (name: CheckName, status: "pass" | "fail" | "skipped", expected?, actual?, detail)
CheckName = line_amounts | subtotal | total | dates | currency
```

Money is `Decimal` on the backend and a string in JSON (`"1450.00"`), so no float rounding reaches the visitor or the CSV.

## Checks

All checks allow a tolerance of 0.01 per term, to absorb rounding on the source document.

| Check | Rule | Skipped when |
|---|---|---|
| `line_amounts` | each `quantity × unit_price` equals `amount` | no line has both quantity and unit price |
| `subtotal` | the sum of line `amount`s equals `subtotal` | no subtotal or no lines |
| `total` | `subtotal − discount + Σ tax amounts` equals `total`. With no subtotal, use the sum of the lines | no total |
| `dates` | `due_date` is not before `issue_date`, and neither is more than a year in the future | either date missing |
| `currency` | a valid ISO 4217 code | currency missing |

A failed check names the numbers ("Lines add up to 1,240.00 but the subtotal says 1,204.00") so the visitor can see what's wrong.

## Pipeline

1. **Read the file.** For a PDF with a text layer, extract per-page text (reuse `core/pdf.py`) and also render the pages to images. For a scanned PDF or a photo, use images only. Rendering needs a small PDF rasterizer. Pick one that installs as a wheel on Render's free tier and fits in 512 MB; check with a real install and a memory reading.
2. **Ask the model.** One JSON-mode call (`complete_json`, same fallback chain) with the images, the text if there is one, and the schema minus `checks`. Plain strings, no Markdown. Unknown fields are `null`, never guessed.
3. **Validate.** pydantic at the boundary, one retry with the validation error, as in demo 2.
4. **Check.** Run the checks above in pure functions.

Image input goes through the OpenAI-compatible `image_url` content part with a base64 data URL. Confirm against live Gemini that this works, and how many images one request accepts, before you build on it. If Gemini's OpenAI-compatible endpoint can't take images, stop and report back rather than switching providers.

## API

Same error shape and codes as [api.md](api.md). Reuses the rate limiter and the size check.

### POST /api/invoices/extract

Multipart field `file`. `200`:

```json
{
  "file_name": "acme-2026-031.pdf",
  "invoice": {
    "document_type": "invoice",
    "vendor": { "name": "Acme Supplies Ltd", "address": "...", "tax_id": "GB123456789", "email": null },
    "customer": { "name": "Northwind Cafe", "address": "...", "tax_id": null, "email": null },
    "invoice_number": "INV-2026-031",
    "issue_date": "2026-09-30",
    "due_date": "2026-10-30",
    "currency": "GBP",
    "line_items": [
      { "description": "Espresso beans 1 kg", "quantity": "10", "unit_price": "18.50", "amount": "185.00" }
    ],
    "subtotal": "185.00",
    "taxes": [{ "label": "VAT", "rate_percent": "20", "amount": "37.00" }],
    "discount": null,
    "total": "222.00",
    "checks": [
      { "name": "line_amounts", "status": "pass", "expected": null, "actual": null, "detail": "All 1 line amounts match quantity × price." },
      { "name": "subtotal", "status": "pass", "expected": "185.00", "actual": "185.00", "detail": "Lines add up to the subtotal." },
      { "name": "total", "status": "pass", "expected": "222.00", "actual": "222.00", "detail": "Subtotal plus tax equals the total." }
    ]
  }
}
```

Extra errors: `400 unsupported_file` for anything that isn't a PDF or a supported image, and `413 file_too_large` naming the page or size limit.

## Frontend: `/invoices`

- Same shell, notice bar and "waking up" handling as the other demos.
- Multi-file upload (PDF and images). Each file gets a card with its own state: queued, extracting, done or failed. Files are sent one at a time.
- Done card: vendor, number, dates and total at the top. Then a line-items table, the tax and totals block, and a checks row with a pass/fail/skipped label per check. The label carries text, not colour alone. A thumbnail of the file opens the original in a new tab.
- Batch actions: "Download CSV" (one row per line item, with the invoice fields repeated, and RFC 4180 quoting), and "Download JSON" (an array of results).
- "Try sample invoices" loads two invented samples: a clean PDF invoice, and a photographed-looking receipt image with one deliberate arithmetic error, so a visitor sees a failed check. Fictional names only.
- Mark the card on `/` live and link it.
