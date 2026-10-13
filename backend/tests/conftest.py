from typing import Optional

import pytest
from fastapi.testclient import TestClient
from fpdf import FPDF

from app.core.config import Settings
from app.main import create_app


def make_settings(**overrides) -> Settings:
    values = {"llm_provider": "fake", "rate_limit_per_minute": 1000, **overrides}
    return Settings(_env_file=None, **values)


def make_pdf(pages: list[Optional[str]]) -> bytes:
    """One PDF page per entry; None makes a blank page."""
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    for text in pages:
        pdf.add_page()
        if text:
            pdf.multi_cell(0, 6, text)
    return bytes(pdf.output())


@pytest.fixture
def make_client():
    clients = []

    def factory(**overrides) -> TestClient:
        client = TestClient(create_app(make_settings(**overrides)))
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def upload(
    client: TestClient,
    session_id: str,
    data: bytes,
    name: str = "doc.pdf",
    content_type: str = "application/pdf",
    headers: Optional[dict] = None,
):
    return client.post(
        f"/api/sessions/{session_id}/documents",
        files={"file": (name, data, content_type)},
        headers=headers,
    )


def new_session(client: TestClient) -> str:
    response = client.post("/api/sessions")
    assert response.status_code == 201
    return response.json()["session_id"]
