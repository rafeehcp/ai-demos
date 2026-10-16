from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.demos.invoices.checks import (
    check_currency,
    check_dates,
    check_line_amounts,
    check_subtotal,
    check_total,
    run_checks,
)
from app.demos.invoices.schema import Invoice, InvoiceFields, LineItem

TODAY = date(2026, 10, 16)


def line(amount: str, quantity: str | None = None, unit_price: str | None = None, description: str = "Item") -> LineItem:
    return LineItem(description=description, quantity=quantity, unit_price=unit_price, amount=amount)


def fields(**values) -> InvoiceFields:
    return InvoiceFields.model_validate({"document_type": "invoice", **values})


def test_line_amounts_pass_when_every_priced_line_matches():
    result = check_line_amounts([line("185.00", "10", "18.50"), line("27.75", "1.5", "18.50"), line("5.00")])
    assert (result.status, result.detail) == ("pass", "All 2 line amounts match quantity × price.")


def test_line_amounts_fail_names_each_wrong_line():
    result = check_line_amounts([line("10.00", "2", "5.00"), line("15.40", "3", "4.50"), line("9.00", "2", "4.00")])
    assert result.status == "fail"
    assert result.detail == (
        "Line 2: 3 × 4.50 is 13.50 but the amount says 15.40. Line 3: 2 × 4.00 is 8.00 but the amount says 9.00."
    )
    assert (result.expected, result.actual) == (Decimal("13.50"), Decimal("15.40"))


def test_line_amounts_skipped_when_no_line_has_quantity_and_price():
    result = check_line_amounts([line("10.00", quantity="2"), line("4.00", unit_price="4.00")])
    assert result.status == "skipped"


@pytest.mark.parametrize("amount, status", [("10.01", "pass"), ("9.99", "pass"), ("10.02", "fail"), ("9.98", "fail")])
def test_line_amount_tolerance_is_one_cent(amount, status):
    assert check_line_amounts([line(amount, "2", "5.00")]).status == status


def test_subtotal_pass_and_fail_with_named_numbers():
    lines = [line("1000.00"), line("240.00")]
    assert check_subtotal(lines, Decimal("1240.00")).status == "pass"
    result = check_subtotal(lines, Decimal("1204.00"))
    assert result.status == "fail"
    assert result.detail == "Lines add up to 1,240.00 but the subtotal says 1,204.00."
    assert (result.expected, result.actual) == (Decimal("1240.00"), Decimal("1204.00"))


@pytest.mark.parametrize("lines, subtotal", [([line("5.00")], None), ([], Decimal("5.00"))])
def test_subtotal_skipped_without_subtotal_or_lines(lines, subtotal):
    assert check_subtotal(lines, subtotal).status == "skipped"


@pytest.mark.parametrize(
    "lines, subtotal, status",
    [
        (["10.00"], "10.01", "pass"),
        (["10.00"], "10.02", "fail"),
        # 0.01 per summed line: rounding on each printed line can add up.
        (["10.00", "5.00"], "15.02", "pass"),
        (["10.00", "5.00"], "15.03", "fail"),
    ],
)
def test_subtotal_tolerance_is_one_cent_per_line(lines, subtotal, status):
    assert check_subtotal([line(a) for a in lines], Decimal(subtotal)).status == status


def test_total_with_discount_and_two_taxes():
    invoice = fields(
        subtotal="1000.00",
        discount="100.00",
        taxes=[{"label": "CGST", "amount": "81.00"}, {"label": "SGST", "amount": "81.00"}],
        total="1062.00",
    )
    result = check_total(invoice)
    assert (result.status, result.detail) == ("pass", "Subtotal minus discount plus tax equals the total.")
    assert result.expected == Decimal("1062.00")


def test_total_fail_names_the_numbers():
    invoice = fields(subtotal="185.00", taxes=[{"label": "VAT", "amount": "37.00"}], total="232.00")
    result = check_total(invoice)
    assert result.status == "fail"
    assert result.detail == "Subtotal plus tax comes to 222.00 but the total says 232.00."


def test_total_treats_a_negative_discount_like_a_positive_one():
    invoice = fields(subtotal="100.00", discount="-10.00", total="90.00")
    assert check_total(invoice).status == "pass"


def test_total_without_subtotal_adds_up_the_lines():
    invoice = fields(
        line_items=[{"description": "a", "amount": "12.00"}, {"description": "b", "amount": "8.00"}],
        taxes=[{"label": "Tax", "amount": "2.00"}],
        total="22.00",
    )
    result = check_total(invoice)
    assert (result.status, result.detail) == ("pass", "Line amounts plus tax equals the total.")
    assert result.expected == Decimal("22.00")


@pytest.mark.parametrize(
    "values",
    [
        {"subtotal": "10.00"},
        {"total": "10.00"},
    ],
)
def test_total_skipped_without_total_or_anything_to_add(values):
    assert check_total(fields(**values)).status == "skipped"


@pytest.mark.parametrize("total, status", [("100.01", "pass"), ("100.02", "fail")])
def test_total_tolerance_with_a_single_term(total, status):
    assert check_total(fields(subtotal="100.00", total=total)).status == status


@pytest.mark.parametrize(
    "issue, due, status",
    [
        (date(2026, 9, 30), date(2026, 10, 30), "pass"),
        (date(2026, 9, 30), date(2026, 9, 30), "pass"),
        (date(2026, 9, 30), date(2026, 9, 1), "fail"),
        (date(2026, 9, 30), date(2027, 10, 16), "pass"),
        (date(2026, 9, 30), date(2027, 10, 17), "fail"),
        (None, date(2026, 10, 30), "skipped"),
        (date(2026, 9, 30), None, "skipped"),
    ],
)
def test_dates(issue, due, status):
    assert check_dates(issue, due, TODAY).status == status


def test_dates_fail_names_the_dates():
    result = check_dates(date(2026, 9, 30), date(2026, 9, 1), TODAY)
    assert result.detail == "The due date 2026-09-01 is before the issue date 2026-09-30."


@pytest.mark.parametrize("code, status", [("GBP", "pass"), ("INR", "pass"), ("$", "fail"), ("EURO", "fail"), (None, "skipped")])
def test_currency(code, status):
    assert check_currency(code).status == status


def test_currency_code_is_trimmed_and_uppercased_at_the_boundary():
    assert fields(currency=" gbp ").currency == "GBP"


@pytest.mark.parametrize(
    "raw, expected",
    [("1,450.00", Decimal("1450.00")), (" 12.5 ", Decimal("12.5")), (18.5, Decimal("18.5")), ("-3.00", Decimal("-3.00"))],
)
def test_money_accepts_plain_and_grouped_numbers(raw, expected):
    assert line(raw).amount == expected


@pytest.mark.parametrize("raw", ["$12.00", "1.234,56", "12%", "NaN"])
def test_money_rejects_anything_that_is_not_a_plain_number(raw):
    with pytest.raises(ValidationError):
        line(raw)


def test_money_stays_decimal_and_serializes_as_strings():
    # 0.1 + 0.2 is 0.30000000000000004 in floats, which would fail an exact-string comparison.
    invoice = fields(
        line_items=[{"description": "a", "amount": 0.1}, {"description": "b", "amount": "0.2"}],
        subtotal="0.30",
        total="0.30",
    )
    out = Invoice(**invoice.model_dump(), checks=run_checks(invoice, TODAY)).model_dump(mode="json")
    assert [item["amount"] for item in out["line_items"]] == ["0.1", "0.2"]
    assert (out["subtotal"], out["total"]) == ("0.30", "0.30")
    subtotal_check = next(c for c in out["checks"] if c["name"] == "subtotal")
    assert (subtotal_check["status"], subtotal_check["expected"], subtotal_check["actual"]) == ("pass", "0.3", "0.30")


def test_run_checks_returns_every_check_in_display_order():
    names = [c.name.value for c in run_checks(fields(), TODAY)]
    assert names == ["line_amounts", "subtotal", "total", "dates", "currency"]


def test_a_party_with_nothing_filled_in_is_null():
    empty = {"name": None, "address": None, "tax_id": None, "email": ""}
    assert fields(customer=empty).customer is None
    assert fields(customer={"name": "Quillon Design Studio"}).customer.name == "Quillon Design Studio"
