"""Arithmetic and sanity checks on an extracted invoice. Pure functions: the
model never decides whether its own numbers add up."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from app.demos.invoices.schema import Check, CheckName, InvoiceFields, LineItem

# Per term in a sum, to absorb rounding on the source document.
TOLERANCE = Decimal("0.01")
_FUTURE_LIMIT = timedelta(days=365)

# Active ISO 4217 codes, plus a few recently replaced ones that still appear on invoices.
ISO_4217 = frozenset(
    """
    AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD
    BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUP CVE CZK DJF DKK DOP DZD
    EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD
    IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL
    MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN
    PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SLL SOS SRD SSP
    STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED
    VES VND VUV WST XAF XAG XAU XBA XBB XBC XBD XCD XCG XDR XOF XPD XPF XPT XSU XUA YER ZAR
    ZMW ZWG ZWL
    """.split()
)


def run_checks(invoice: InvoiceFields, today: date) -> list[Check]:
    return [
        check_line_amounts(invoice.line_items),
        check_subtotal(invoice.line_items, invoice.subtotal),
        check_total(invoice),
        check_dates(invoice.issue_date, invoice.due_date, today),
        check_currency(invoice.currency),
    ]


def check_line_amounts(lines: list[LineItem]) -> Check:
    name = CheckName.line_amounts
    priced = [(n, line) for n, line in enumerate(lines, start=1) if line.quantity is not None and line.unit_price is not None]
    if not priced:
        return Check(name=name, status="skipped", detail="No line shows both a quantity and a unit price.")
    wrong = []
    for n, line in priced:
        product = line.quantity * line.unit_price
        if not _close(product, line.amount, terms=1):
            wrong.append((n, line, _display_product(line)))
    if not wrong:
        detail = (
            "The line amount matches quantity × price."
            if len(priced) == 1
            else f"All {len(priced)} line amounts match quantity × price."
        )
        return Check(name=name, status="pass", detail=detail)
    first_n, first, first_product = wrong[0]
    detail = " ".join(
        f"Line {n}: {_fmt(line.quantity)} × {_fmt(line.unit_price)} is {_fmt(product)} "
        f"but the amount says {_fmt(line.amount)}."
        for n, line, product in wrong
    )
    return Check(name=name, status="fail", expected=first_product, actual=first.amount, detail=detail)


def check_subtotal(lines: list[LineItem], subtotal: Optional[Decimal]) -> Check:
    name = CheckName.subtotal
    if subtotal is None:
        return Check(name=name, status="skipped", detail="No subtotal on the document.")
    if not lines:
        return Check(name=name, status="skipped", detail="No line items to add up.")
    lines_sum = sum((line.amount for line in lines), Decimal(0))
    if _close(lines_sum, subtotal, terms=len(lines)):
        return Check(name=name, status="pass", expected=lines_sum, actual=subtotal, detail="Lines add up to the subtotal.")
    return Check(
        name=name,
        status="fail",
        expected=lines_sum,
        actual=subtotal,
        detail=f"Lines add up to {_fmt(lines_sum)} but the subtotal says {_fmt(subtotal)}.",
    )


def check_total(invoice: InvoiceFields) -> Check:
    name = CheckName.total
    total = invoice.total
    if total is None:
        return Check(name=name, status="skipped", detail="No total on the document.")
    if invoice.subtotal is not None:
        base, base_terms, words = invoice.subtotal, 1, "Subtotal"
    elif invoice.line_items:
        base = sum((line.amount for line in invoice.line_items), Decimal(0))
        base_terms, words = len(invoice.line_items), "Line amounts"
    else:
        return Check(name=name, status="skipped", detail="No subtotal or line items to add up to the total.")

    # Documents print a discount as "-10.00" or "10.00"; either way it comes off.
    discount = abs(invoice.discount) if invoice.discount is not None else Decimal(0)
    tax = sum((t.amount for t in invoice.taxes), Decimal(0))
    expected = base - discount + tax
    terms = base_terms + (invoice.discount is not None) + len(invoice.taxes)
    if invoice.discount is not None:
        words += " minus discount"
    if invoice.taxes:
        words += " plus tax"

    if _close(expected, total, terms=terms):
        return Check(name=name, status="pass", expected=expected, actual=total, detail=f"{words} equals the total.")
    return Check(
        name=name,
        status="fail",
        expected=expected,
        actual=total,
        detail=f"{words} comes to {_fmt(expected)} but the total says {_fmt(total)}.",
    )


def check_dates(issue: Optional[date], due: Optional[date], today: date) -> Check:
    name = CheckName.dates
    if issue is None or due is None:
        return Check(name=name, status="skipped", detail="Needs both an issue date and a due date.")
    problems = []
    if due < issue:
        problems.append(f"The due date {due.isoformat()} is before the issue date {issue.isoformat()}.")
    for label, value in (("issue", issue), ("due", due)):
        if value > today + _FUTURE_LIMIT:
            problems.append(f"The {label} date {value.isoformat()} is more than a year from today.")
    if problems:
        return Check(name=name, status="fail", detail=" ".join(problems))
    return Check(name=name, status="pass", detail="The due date is on or after the issue date.")


def check_currency(code: Optional[str]) -> Check:
    name = CheckName.currency
    if code is None:
        return Check(name=name, status="skipped", detail="No currency on the document.")
    if code in ISO_4217:
        return Check(name=name, status="pass", detail=f"{code} is a valid ISO 4217 currency code.")
    return Check(name=name, status="fail", detail=f"“{code}” is not an ISO 4217 currency code.")


def _close(computed: Decimal, printed: Decimal, *, terms: int) -> bool:
    return abs(computed - printed) <= TOLERANCE * terms


def _display_product(line: LineItem) -> Decimal:
    """quantity × unit_price at the precision the line is printed in, so 1.5 × 18.50 reads 27.75, not 27.750."""
    places = max(-n.as_tuple().exponent for n in (line.quantity, line.unit_price, line.amount))
    return (line.quantity * line.unit_price).quantize(Decimal(1).scaleb(-max(places, 0)), rounding=ROUND_HALF_UP)


def _fmt(value: Decimal) -> str:
    return f"{value:,}"
