"""Write the invented sample invoices, and the values printed on each.

    .venv/Scripts/python scripts/sample_invoices.py ../frontend/public/samples

sample-invoice.pdf and sample-receipt.jpg are what the frontend's "Try sample
invoices" button uploads. The receipt's subtotal is deliberately wrong, so the
subtotal check fails. The other two files are not shipped: they are for
checking extraction by hand (see invoice_accuracy.py). Every name, address and
number in them is made up.
"""

import random
import sys
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, Optional

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFilter, ImageFont

NOTE = "SAMPLE DOCUMENT. All names, places and figures are fictional."


@dataclass(frozen=True)
class Line:
    description: str
    quantity: Optional[str]
    unit_price: Optional[str]
    amount: str


@dataclass(frozen=True)
class Sample:
    """The values printed on a document, which is what a perfect extraction returns."""

    file_name: str
    document_type: str
    vendor: dict
    customer: Optional[dict]
    invoice_number: Optional[str]
    issue_date: Optional[date]
    due_date: Optional[date]
    currency: str
    line_items: list[Line]
    subtotal: Optional[str]
    taxes: list[dict]
    discount: Optional[str]
    total: str
    # Check name to status, for the checks this document is built to exercise.
    expected_checks: dict = field(default_factory=dict)
    shipped: bool = False


def party(name, address=None, tax_id=None, email=None) -> dict:
    return {"name": name, "address": address, "tax_id": tax_id, "email": email}


SAMPLE_INVOICE = Sample(
    file_name="sample-invoice.pdf",
    document_type="invoice",
    vendor=party("Fernhill Paper Co.", "Unit 7, Tanner's Yard, Ashbury AB4 2QT, United Kingdom", "GB 000 4417 21", "accounts@fernhill-paper.example"),
    customer=party("Quillon Design Studio", "22 Marlow Street, Ashbury AB1 6LD, United Kingdom"),
    invoice_number="FPC-2026-0931",
    issue_date=date(2026, 9, 30),
    due_date=date(2026, 10, 30),
    currency="GBP",
    line_items=[
        Line("Recycled card stock A4, pack of 250", "10", "18.50", "185.00"),
        Line("Kraft envelopes C5, box of 500", "4", "32.00", "128.00"),
        Line("Letterpress business cards, set of 200", "2", "64.75", "129.50"),
        Line("Next-day delivery", "1", "12.00", "12.00"),
    ],
    subtotal="454.50",
    taxes=[{"label": "VAT", "rate_percent": "20", "amount": "90.90"}],
    discount=None,
    total="545.40",
    expected_checks={"line_amounts": "pass", "subtotal": "pass", "total": "pass", "dates": "pass", "currency": "pass"},
    shipped=True,
)

# Lines add up to 25.95; the printed subtotal says 26.95.
SAMPLE_RECEIPT = Sample(
    file_name="sample-receipt.jpg",
    document_type="receipt",
    vendor=party("Copperleaf Cafe", "418 Orchard Ave, Millbrook OR"),
    customer=None,
    invoice_number="4471",
    issue_date=date(2026, 10, 3),
    due_date=None,
    currency="USD",
    line_items=[
        Line("Flat white", "2", "4.20", "8.40"),
        Line("Almond croissant", "1", "3.85", "3.85"),
        Line("Avocado toast", "1", "9.50", "9.50"),
        Line("Sparkling water", "2", "2.10", "4.20"),
    ],
    subtotal="26.95",
    taxes=[{"label": "Sales tax", "rate_percent": "8", "amount": "2.16"}],
    discount=None,
    total="29.11",
    expected_checks={"line_amounts": "pass", "subtotal": "fail", "total": "pass", "dates": "skipped", "currency": "pass"},
    shipped=True,
)

DISCOUNT_TWO_TAXES = Sample(
    file_name="extra-discount-two-taxes.pdf",
    document_type="invoice",
    vendor=party("Northpine Outfitters Ltd.", "1180 Cedar Bluff Road, Vancouver, BC V5K 0A0, Canada", "GST 700000001 RT0001", "billing@northpine.example"),
    customer=party("Ravenmoor Trail Club", "PO Box 311, Squamish, BC V8B 0A0, Canada"),
    invoice_number="NPO-55120",
    issue_date=date(2026, 10, 2),
    due_date=date(2026, 11, 1),
    currency="CAD",
    line_items=[
        Line("Trail backpack 40 L", "6", "129.00", "774.00"),
        Line("Rechargeable headlamp", "6", "34.50", "207.00"),
        Line("Gravity water filter", "3", "48.25", "144.75"),
        Line("Group first aid kit", "2", "56.80", "113.60"),
        Line("Regional trail map set", "6", "12.40", "74.40"),
    ],
    subtotal="1313.75",
    taxes=[
        {"label": "GST", "rate_percent": "5", "amount": "59.12"},
        {"label": "PST", "rate_percent": "7", "amount": "82.77"},
    ],
    discount="131.38",
    total="1324.26",
    expected_checks={"line_amounts": "pass", "subtotal": "pass", "total": "pass", "dates": "pass", "currency": "pass"},
)

GERMAN_EUR = Sample(
    file_name="extra-eur-scan.png",
    document_type="invoice",
    vendor=party("Kranich Werkstatt GmbH", "Lindenauer Ring 14, 04177 Leipzig, Deutschland", "DE999888777"),
    customer=party("Atelier Lindgrau", "Brunnenweg 3, 01067 Dresden, Deutschland"),
    invoice_number="RE-2026-0412",
    issue_date=date(2026, 9, 4),
    due_date=date(2026, 9, 18),
    currency="EUR",
    line_items=[
        Line("Schreibtisch Eiche massiv", "2", "1249.00", "2498.00"),
        Line("Buerostuhl ergonomisch", "3", "389.90", "1169.70"),
        Line("Montage vor Ort (Stunden)", "4", "65.00", "260.00"),
    ],
    subtotal="3927.70",
    taxes=[{"label": "USt", "rate_percent": "19", "amount": "746.26"}],
    discount=None,
    total="4673.96",
    expected_checks={"line_amounts": "pass", "subtotal": "pass", "total": "pass", "dates": "pass", "currency": "pass"},
)

SAMPLES = [SAMPLE_INVOICE, SAMPLE_RECEIPT, DISCOUNT_TWO_TAXES, GERMAN_EUR]


def money_en(value: str) -> str:
    return f"{Decimal(value):,.2f}"


def money_de(value: str) -> str:
    return money_en(value).replace(",", "_").replace(".", ",").replace("_", ".")


def _fpdf_invoice(sample: Sample, path: Path, *, title: str, date_text: Callable[[date], str], labels: dict) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, sample.vendor["name"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    for text in (sample.vendor["address"], f"{labels['tax_id']}: {sample.vendor['tax_id']}", sample.vendor["email"]):
        pdf.cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for label, value in (
        (labels["number"], sample.invoice_number),
        (labels["issued"], date_text(sample.issue_date)),
        (labels["due"], date_text(sample.due_date)),
    ):
        pdf.cell(35, 6, label)
        pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, labels["bill_to"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 5, sample.customer["name"], new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, sample.customer["address"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    widths = (95, 20, 35, 40)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(235, 235, 235)
    for width, text, align in zip(widths, labels["columns"], "LRRR"):
        pdf.cell(width, 8, text, align=align, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", size=10)
    for line in sample.line_items:
        pdf.cell(widths[0], 7, line.description)
        pdf.cell(widths[1], 7, line.quantity, align="R")
        pdf.cell(widths[2], 7, money_en(line.unit_price), align="R")
        pdf.cell(widths[3], 7, money_en(line.amount), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    def total_row(label: str, value: str, bold: bool = False) -> None:
        pdf.set_font("Helvetica", "B" if bold else "", 10)
        pdf.cell(widths[0] + widths[1] + widths[2], 7, label, align="R")
        pdf.cell(widths[3], 7, value, align="R", new_x="LMARGIN", new_y="NEXT")

    total_row(labels["subtotal"], money_en(sample.subtotal))
    if sample.discount:
        total_row(labels["discount"], "-" + money_en(sample.discount))
    for tax in sample.taxes:
        total_row(f"{tax['label']} {tax['rate_percent']}%", money_en(tax["amount"]))
    total_row(f"{labels['total']} ({sample.currency})", money_en(sample.total), bold=True)
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, labels["terms"] + "\n" + NOTE)
    pdf.output(str(path))


def write_sample_invoice(path: Path) -> None:
    _fpdf_invoice(
        SAMPLE_INVOICE,
        path,
        title="INVOICE",
        date_text=lambda d: d.isoformat(),
        labels={
            "tax_id": "VAT reg. no.",
            "number": "Invoice no.",
            "issued": "Issue date",
            "due": "Due date",
            "bill_to": "Bill to",
            "columns": ("Description", "Qty", "Unit price", "Amount"),
            "subtotal": "Subtotal",
            "discount": "Discount",
            "total": "Total due",
            "terms": "Payment within 30 days by bank transfer to sort code 00-00-00, account 00000000.",
        },
    )


def write_discount_two_taxes(path: Path) -> None:
    sample = DISCOUNT_TWO_TAXES
    _fpdf_invoice(
        sample,
        path,
        title="INVOICE",
        date_text=lambda d: f"{d:%B} {d.day}, {d.year}",
        labels={
            "tax_id": "Business no.",
            "number": "Invoice #",
            "issued": "Date",
            "due": "Payment due",
            "bill_to": "Sold to",
            "columns": ("Item", "Qty", "Price", "Line total"),
            "subtotal": "Subtotal",
            "discount": "Club discount 10%",
            "total": "Total",
            "terms": "Net 30. GST and PST charged on the discounted subtotal.",
        },
    )


def _font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def write_sample_receipt(path: Path) -> None:
    sample = SAMPLE_RECEIPT
    rows: list[tuple[str, str]] = [
        ("COPPERLEAF CAFE", ""),
        (sample.vendor["address"], ""),
        ("", ""),
        (f"Order {sample.invoice_number}", "10/03/2026 08:42"),
        ("", ""),
    ]
    for line in sample.line_items:
        rows.append((f"{line.quantity} x {line.description}", ""))
        rows.append((f"    @ {line.unit_price}", line.amount))
    rows += [
        ("", ""),
        ("SUBTOTAL", sample.subtotal),
        ("Sales tax 8%", sample.taxes[0]["amount"]),
        ("TOTAL USD", sample.total),
        ("", ""),
        ("VISA ****0000", sample.total),
        ("", ""),
        ("Thank you!", ""),
        ("Sample receipt. Fictional.", ""),
    ]
    font, line_height, width = _font(26), 38, 560
    paper = Image.new("RGB", (width, 60 + line_height * len(rows)), (250, 248, 240))
    draw = ImageDraw.Draw(paper)
    for i, (left, right) in enumerate(rows):
        y = 30 + i * line_height
        draw.text((30, y), left, fill=(40, 40, 45), font=font)
        if right:
            draw.text((width - 30, y), right, fill=(40, 40, 45), font=font, anchor="ra")

    rng = random.Random(7)
    paper = paper.rotate(-3, expand=True, fillcolor=(0, 0, 0, 0), resample=Image.BICUBIC)
    background = Image.new("RGB", (paper.width + 160, paper.height + 160), (96, 72, 54))
    noise = Image.effect_noise(background.size, 18).convert("RGB")
    background = Image.blend(background, noise, 0.15)
    mask = paper.convert("L").point(lambda v: 255 if v > 0 else 0)
    background.paste(paper, (80 + rng.randint(-10, 10), 80), mask)
    shade = Image.linear_gradient("L").resize(background.size).point(lambda v: 255 - v // 5)
    background = Image.composite(background, Image.new("RGB", background.size, (0, 0, 0)), shade)
    background.filter(ImageFilter.GaussianBlur(0.8)).save(path, "JPEG", quality=72)


def write_german_scan(path: Path) -> None:
    sample = GERMAN_EUR
    font, bold, small = _font(24), _font(34), _font(18)
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    y = 80

    def text(x: int, value: str, use=font, anchor="la") -> None:
        draw.text((x, y), value, fill=(20, 20, 20), font=use, anchor=anchor)

    text(90, sample.vendor["name"], bold)
    y += 50
    text(90, sample.vendor["address"], small)
    y += 30
    text(90, f"USt-IdNr.: {sample.vendor['tax_id']}", small)
    y += 90
    text(90, sample.customer["name"])
    y += 34
    text(90, sample.customer["address"])
    y += 90
    text(90, "RECHNUNG", bold)
    y += 60
    for label, value in (
        ("Rechnungsnummer", sample.invoice_number),
        ("Rechnungsdatum", f"{sample.issue_date:%d.%m.%Y}"),
        ("Zahlbar bis", f"{sample.due_date:%d.%m.%Y}"),
    ):
        text(90, label)
        text(420, value)
        y += 36
    y += 40
    columns = ((90, "Pos. Bezeichnung", "la"), (760, "Menge", "ra"), (960, "Einzelpreis", "ra"), (1150, "Betrag EUR", "ra"))
    for x, label, anchor in columns:
        text(x, label, anchor=anchor)
    y += 40
    draw.line((90, y, 1150, y), fill=(20, 20, 20), width=2)
    y += 16
    for n, line in enumerate(sample.line_items, start=1):
        text(90, f"{n}   {line.description}")
        text(760, line.quantity, anchor="ra")
        text(960, money_de(line.unit_price), anchor="ra")
        text(1150, money_de(line.amount), anchor="ra")
        y += 40
    y += 20
    for label, value in (
        ("Nettobetrag", sample.subtotal),
        (f"zzgl. USt {sample.taxes[0]['rate_percent']} %", sample.taxes[0]["amount"]),
        ("Gesamtbetrag", sample.total),
    ):
        text(960, label, anchor="ra")
        text(1150, money_de(value), anchor="ra")
        y += 40
    y += 60
    text(90, "Zahlbar innerhalb von 14 Tagen ohne Abzug.", small)
    y += 30
    text(90, "Musterdokument. Alle Namen und Zahlen sind erfunden.", small)
    # A flatbed scan: slightly grey paper, a hair of tilt and blur.
    scan = image.rotate(0.6, expand=False, fillcolor="white", resample=Image.BICUBIC)
    scan = Image.blend(scan, Image.new("RGB", scan.size, (238, 236, 230)), 0.25)
    scan.filter(ImageFilter.GaussianBlur(0.6)).save(path, "PNG")


WRITERS = {
    SAMPLE_INVOICE.file_name: write_sample_invoice,
    SAMPLE_RECEIPT.file_name: write_sample_receipt,
    DISCOUNT_TWO_TAXES.file_name: write_discount_two_taxes,
    GERMAN_EUR.file_name: write_german_scan,
}


def main(out_dir: Path, extras_dir: Path) -> None:
    for sample in SAMPLES:
        target = (out_dir if sample.shipped else extras_dir) / sample.file_name
        target.parent.mkdir(parents=True, exist_ok=True)
        WRITERS[sample.file_name](target)
        print(f"wrote {target}")


if __name__ == "__main__":
    shipped = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    main(shipped, Path(sys.argv[2]) if len(sys.argv) > 2 else shipped)
