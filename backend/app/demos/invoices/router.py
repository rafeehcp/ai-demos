from datetime import date

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from app.core.config import Settings
from app.core.deps import get_llm, get_settings, rate_limited
from app.core.errors import AppError
from app.core.llm import LLMProvider
from app.demos.invoices.document import read_document
from app.demos.invoices.extract import extract_invoice
from app.demos.invoices.schema import Invoice


class ExtractOut(BaseModel):
    file_name: str
    invoice: Invoice


router = APIRouter(prefix="/api/invoices")


@router.post("/extract", response_model=ExtractOut, dependencies=[Depends(rate_limited)])
async def extract(
    file: UploadFile | None = File(None),
    settings: Settings = Depends(get_settings),
    llm: LLMProvider = Depends(get_llm),
) -> ExtractOut:
    if file is None:
        raise AppError(400, "unsupported_file", "Choose a PDF or an image to upload.")
    data = await file.read(settings.max_file_mb * 1024 * 1024 + 1)
    document = read_document(data, max_mb=settings.max_file_mb, max_pages=settings.invoice_max_pages)
    return ExtractOut(
        file_name=file.filename or "invoice",
        invoice=await extract_invoice(llm, document, date.today()),
    )
