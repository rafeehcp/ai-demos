import re
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, BeforeValidator

_GROUPED_THOUSANDS = re.compile(r"-?\d{1,3}(,\d{3})+(\.\d+)?")


def _plain_number(value: object) -> object:
    """Accept "1,450.00" as well as "1450.00". Anything else that isn't a plain
    number fails validation, so the model is asked again rather than guessed at."""
    if not isinstance(value, str):
        return value
    text = value.strip().replace(" ", "")
    if text == "":
        return None
    if _GROUPED_THOUSANDS.fullmatch(text):
        return text.replace(",", "")
    return text


def _currency_code(value: object) -> object:
    if isinstance(value, str):
        return value.strip().upper() or None
    return value


Money = Annotated[Decimal, BeforeValidator(_plain_number)]


class Party(BaseModel):
    name: str
    address: Optional[str] = None
    tax_id: Optional[str] = None
    email: Optional[str] = None


class LineItem(BaseModel):
    description: str
    quantity: Optional[Money] = None
    unit_price: Optional[Money] = None
    amount: Money


class Tax(BaseModel):
    label: str
    rate_percent: Optional[Money] = None
    amount: Money


DocumentType = Literal["invoice", "receipt", "credit_note", "other"]


class InvoiceFields(BaseModel):
    """What the model reads off the document."""

    document_type: DocumentType
    vendor: Optional[Party] = None
    customer: Optional[Party] = None
    invoice_number: Optional[str] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Annotated[Optional[str], BeforeValidator(_currency_code)] = None
    line_items: list[LineItem] = []
    subtotal: Optional[Money] = None
    taxes: list[Tax] = []
    discount: Optional[Money] = None
    total: Optional[Money] = None


class CheckName(str, Enum):
    """Declaration order is display order."""

    line_amounts = "line_amounts"
    subtotal = "subtotal"
    total = "total"
    dates = "dates"
    currency = "currency"


class Check(BaseModel):
    name: CheckName
    status: Literal["pass", "fail", "skipped"]
    expected: Optional[Decimal] = None
    actual: Optional[Decimal] = None
    detail: str


class Invoice(InvoiceFields):
    checks: list[Check]
