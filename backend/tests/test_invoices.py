import base64
import io

import pytest
from PIL import Image

from app.core.llm import LLMBadJSON
from app.demos.invoices.document import PHOTO_PIXELS
from tests.conftest import ScriptedJSON, make_pdf, new_session, upload
from tests.test_api import error_of

INVOICE_TEXT = "INVOICE INV-2026-031\nFernhill Paper Co.\nRecycled card stock 10 x 18.50 = 185.00"


def reply(**overrides) -> dict:
    data = {
        "document_type": "invoice",
        "vendor": {"name": "Fernhill Paper Co.", "address": None, "tax_id": None, "email": None},
        "customer": None,
        "invoice_number": "INV-2026-031",
        "issue_date": "2026-09-30",
        "due_date": "2026-10-30",
        "currency": "GBP",
        "line_items": [{"description": "Recycled card stock", "quantity": "10", "unit_price": "18.50", "amount": "185.00"}],
        "subtotal": "185.00",
        "taxes": [{"label": "VAT", "rate_percent": "20", "amount": "37.00"}],
        "discount": None,
        "total": "222.00",
    }
    data.update(overrides)
    return data


def image_bytes(fmt: str = "PNG", size=(400, 600), exif=None) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", size, "white")
    image.save(buffer, fmt, **({"exif": exif} if exif else {}))
    return buffer.getvalue()


def decode(data_url: str) -> Image.Image:
    header, payload = data_url.split(",", 1)
    return Image.open(io.BytesIO(base64.b64decode(payload)))


def extract(client, data: bytes, name: str = "invoice.pdf", content_type: str = "application/pdf", headers=None):
    return client.post("/api/invoices/extract", files={"file": (name, data, content_type)}, headers=headers)


def scripted(client, *replies) -> ScriptedJSON:
    fake = ScriptedJSON(*replies)
    client.app.state.llm.complete_json = fake
    return fake


def test_pdf_with_text_sends_page_text_and_one_image_per_page(client):
    fake = scripted(client, reply())
    response = extract(client, make_pdf([INVOICE_TEXT, "Terms: 30 days net."]))
    assert response.status_code == 200
    prompt, images = fake.prompts[0], fake.images[0]
    assert prompt.index("=== Page 1 ===") < prompt.index("Fernhill Paper Co.") < prompt.index("=== Page 2 ===")
    assert len(images) == 2
    assert all(url.startswith("data:image/png;base64,") for url in images)
    assert max(decode(images[0]).size) == 1600


def test_extract_returns_fields_and_checks_with_money_as_strings(client):
    scripted(client, reply())
    body = extract(client, make_pdf([INVOICE_TEXT]), name="fernhill.pdf").json()
    assert body["file_name"] == "fernhill.pdf"
    invoice = body["invoice"]
    assert (invoice["subtotal"], invoice["total"]) == ("185.00", "222.00")
    assert invoice["line_items"][0] == {"description": "Recycled card stock", "quantity": "10", "unit_price": "18.50", "amount": "185.00"}
    checks = {c["name"]: c for c in invoice["checks"]}
    assert list(checks) == ["line_amounts", "subtotal", "total", "dates", "currency"]
    assert {name: c["status"] for name, c in checks.items()} == {n: "pass" for n in checks}
    assert (checks["total"]["expected"], checks["total"]["actual"]) == ("222.00", "222.00")


def test_a_misread_total_fails_its_check(client):
    scripted(client, reply(total="232.00"))
    checks = {c["name"]: c for c in extract(client, make_pdf([INVOICE_TEXT])).json()["invoice"]["checks"]}
    assert checks["total"]["status"] == "fail"
    assert checks["total"]["detail"] == "Subtotal plus tax comes to 222.00 but the total says 232.00."


def test_scanned_pdf_sends_images_without_a_text_layer(client):
    fake = scripted(client, reply())
    assert extract(client, make_pdf([None])).status_code == 200
    assert "=== Page" not in fake.prompts[0]
    assert len(fake.images[0]) == 1


@pytest.mark.parametrize("fmt, name, mime", [("PNG", "receipt.png", "image/png"), ("JPEG", "receipt.jpg", "image/jpeg"), ("WEBP", "receipt.webp", "image/webp")])
def test_image_upload_is_sent_as_one_jpeg(client, fmt, name, mime):
    fake = scripted(client, reply())
    response = extract(client, image_bytes(fmt), name=name, content_type=mime)
    assert response.status_code == 200
    assert "=== Page" not in fake.prompts[0]
    assert "1 page" in fake.prompts[0]
    [url] = fake.images[0]
    assert url.startswith("data:image/jpeg;base64,")
    assert decode(url).size == (400, 600)


def test_photo_is_turned_upright_and_scaled_down(client):
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotate 90 degrees clockwise to view
    fake = scripted(client, reply())
    extract(client, image_bytes("JPEG", size=(4000, 3000), exif=exif.tobytes()), name="photo.jpg", content_type="image/jpeg")
    assert decode(fake.images[0][0]).size == (PHOTO_PIXELS * 3 // 4, PHOTO_PIXELS)


@pytest.mark.parametrize(
    "data, name, content_type",
    [
        (b"just some text", "notes.txt", "text/plain"),
        (image_bytes("GIF"), "receipt.gif", "image/gif"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "broken.png", "image/png"),
    ],
)
def test_unsupported_or_unreadable_files_are_rejected(client, data, name, content_type):
    assert error_of(extract(client, data, name=name, content_type=content_type)) == (400, "unsupported_file")


def test_missing_file_is_rejected(client):
    assert error_of(client.post("/api/invoices/extract")) == (400, "unsupported_file")


def test_too_many_pages_names_the_invoice_limit(make_client):
    client = make_client(invoice_max_pages=2)
    response = extract(client, make_pdf(["one", "two", "three"]))
    assert error_of(response) == (413, "file_too_large")
    assert "2 pages" in response.json()["error"]["message"]


def test_file_over_the_size_limit_is_rejected(make_client):
    client = make_client(max_file_mb=1)
    response = extract(client, image_bytes("PNG") + b"\x00" * (1024 * 1024), name="big.png", content_type="image/png")
    assert error_of(response) == (413, "file_too_large")
    assert "1 MB" in response.json()["error"]["message"]


def test_bad_reply_is_retried_once_with_the_reason_and_the_same_images(client):
    fake = scripted(client, reply(issue_date="30/09/2026"), reply())
    assert extract(client, make_pdf([INVOICE_TEXT])).status_code == 200
    assert len(fake.prompts) == 2
    assert "issue_date" in fake.prompts[1] and "issue_date" not in fake.prompts[0]
    assert fake.images[1] == fake.images[0]


def test_invalid_json_then_valid_is_one_retry(client):
    fake = scripted(client, LLMBadJSON("The reply was not valid JSON (Expecting value)."), reply())
    assert extract(client, make_pdf([INVOICE_TEXT])).status_code == 200
    assert len(fake.prompts) == 2
    assert "not valid JSON" in fake.prompts[1]


def test_two_bad_replies_are_llm_error(client):
    fake = scripted(client, LLMBadJSON("not JSON"), reply(total="$222"))
    assert error_of(extract(client, make_pdf([INVOICE_TEXT]))) == (502, "llm_error")
    assert len(fake.prompts) == 2


def test_offline_fake_model_returns_an_invoice_that_adds_up(client):
    response = extract(client, make_pdf([INVOICE_TEXT]))
    assert response.status_code == 200
    statuses = {c["name"]: c["status"] for c in response.json()["invoice"]["checks"]}
    assert statuses == {"line_amounts": "pass", "subtotal": "pass", "total": "pass", "dates": "pass", "currency": "pass"}


def test_rate_limit_is_shared_with_chat_and_contracts(make_client):
    client = make_client(rate_limit_per_minute=3)
    ip = {"X-Forwarded-For": "203.0.113.7"}
    session_id = new_session(client)
    assert upload(client, session_id, make_pdf(["text"]), headers=ip).status_code == 201
    contract = client.post("/api/contracts/review", files={"file": ("c.pdf", make_pdf(["A contract."]), "application/pdf")}, headers=ip)
    assert contract.status_code == 200
    assert extract(client, make_pdf([INVOICE_TEXT]), headers=ip).status_code == 200
    assert error_of(extract(client, make_pdf([INVOICE_TEXT]), headers=ip)) == (429, "rate_limited")
    assert error_of(upload(client, session_id, make_pdf(["text"]), headers=ip)) == (429, "rate_limited")
