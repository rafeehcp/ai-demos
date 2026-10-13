from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from app.core.config import Settings
from app.core.deps import get_llm, get_settings, rate_limited
from app.core.errors import AppError
from app.core.llm import LLMProvider
from app.core.pdf import extract_pages
from app.demos.contracts.review import review_contract
from app.demos.contracts.schema import ContractReview


class ReviewOut(BaseModel):
    document_name: str
    pages: int
    review: ContractReview


router = APIRouter(prefix="/api/contracts")


@router.post("/review", response_model=ReviewOut, dependencies=[Depends(rate_limited)])
async def review(
    file: UploadFile | None = File(None),
    settings: Settings = Depends(get_settings),
    llm: LLMProvider = Depends(get_llm),
) -> ReviewOut:
    if file is None:
        raise AppError(400, "not_a_pdf", "Choose a PDF file to upload.")
    data = await file.read(settings.max_file_mb * 1024 * 1024 + 1)
    pages = extract_pages(data, max_mb=settings.max_file_mb, max_pages=settings.contract_max_pages)
    return ReviewOut(
        document_name=file.filename or "contract.pdf",
        pages=len(pages),
        review=await review_contract(llm, pages),
    )
