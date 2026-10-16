import json
from datetime import date

from app.core.llm import LLMProvider, complete_validated
from app.demos.invoices.checks import run_checks
from app.demos.invoices.document import Document
from app.demos.invoices.schema import Invoice, InvoiceFields

_EXAMPLE = {
    "document_type": "invoice",
    "vendor": {
        "name": "Seller name as printed",
        "address": "Seller address on one line, or null",
        "tax_id": "VAT, GST or tax number, or null",
        "email": "Seller email, or null",
    },
    "customer": {"name": "Buyer name as printed", "address": None, "tax_id": None, "email": None},
    "invoice_number": "INV-2026-031",
    "issue_date": "2026-09-30",
    "due_date": "2026-10-30",
    "currency": "GBP",
    "line_items": [
        {"description": "Item text as printed", "quantity": "10", "unit_price": "18.50", "amount": "185.00"}
    ],
    "subtotal": "185.00",
    "taxes": [{"label": "VAT", "rate_percent": "20", "amount": "37.00"}],
    "discount": None,
    "total": "222.00",
}

SYSTEM_PROMPT = f"""You read invoices and receipts and copy their data into JSON.
You get an image of each page, and the page text when the file has a text layer.
Reply with one JSON object and nothing else, shaped like this example:

{json.dumps(_EXAMPLE, indent=2)}

Rules:
- Copy every value from the document. Never calculate, correct or fill in a value: if the document doesn't print a subtotal, "subtotal" is null, and if a line's numbers don't add up, copy them as printed anyway.
- Anything the document doesn't show is null. Never guess.
- document_type is "invoice", "receipt", "credit_note" or "other".
- vendor is the business that issued the document; customer is who it is billed to, or null on most receipts.
- Money, quantities and rates are JSON strings holding a plain number: a dot for decimals, no currency symbol, no thousands separators, no percent sign. Write 1.234,56 as "1234.56".
- Dates are YYYY-MM-DD. A date like 10/03/2026 is month first (October 3) when the vendor is in the United States, which a US state abbreviation in the address or a USD amount shows, and day first (10 March) for most other countries. Decide this from the vendor's address and currency before reading any date.
- currency is the ISO 4217 code, such as "USD", "EUR" or "INR". Use a symbol only when it is unambiguous for the vendor's country.
- line_items: one entry per line of goods or services, in document order. quantity and unit_price are null when the line doesn't show them. amount is the line total as printed.
- taxes: one entry per tax line added to the subtotal, such as VAT, GST or sales tax. label is the tax name alone, without the rate. rate_percent is null when no rate is printed.
- discount: a discount taken off the subtotal, as a positive number. null when there is none.
- total: the final amount due or paid.
- Every text value is plain text: no Markdown, asterisks or bullet points."""



def build_user_prompt(document: Document) -> str:
    pages = len(document.images)
    intro = f"The document has {pages} {'page' if pages == 1 else 'pages'}; an image of each is attached in order."
    if not document.has_text:
        return intro
    text = "\n\n".join(f"=== Page {n} ===\n{t.strip()}" for n, t in enumerate(document.texts, start=1))
    return f"{intro}\nThe text layer of each page follows.\n\n{text}"


async def extract_invoice(llm: LLMProvider, document: Document, today: date) -> Invoice:
    fields = await complete_validated(llm, InvoiceFields, SYSTEM_PROMPT, build_user_prompt(document), document.images)
    return Invoice(**fields.model_dump(), checks=run_checks(fields, today))


def fake_invoice(user: str) -> dict:
    """The offline model's reply: a fixed, invented invoice whose numbers add up."""
    return {
        "document_type": "invoice",
        "vendor": {"name": "Offline Example Supplies", "address": None, "tax_id": None, "email": None},
        "customer": {"name": "Offline Example Customer", "address": None, "tax_id": None, "email": None},
        "invoice_number": "OFFLINE-1",
        "issue_date": "2026-01-15",
        "due_date": "2026-02-14",
        "currency": "USD",
        "line_items": [
            {"description": "Placeholder line, no model read this file", "quantity": "2", "unit_price": "40.00", "amount": "80.00"},
            {"description": "Second placeholder line", "quantity": "1", "unit_price": "20.00", "amount": "20.00"},
        ],
        "subtotal": "100.00",
        "taxes": [{"label": "Sales tax", "rate_percent": "8", "amount": "8.00"}],
        "discount": None,
        "total": "108.00",
    }
