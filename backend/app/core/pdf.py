import io
import logging

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.core.errors import AppError

logger = logging.getLogger(__name__)


def extract_pages(data: bytes, *, max_mb: int, max_pages: int) -> list[str]:
    """Text of each page, in order. Raises AppError for anything the visitor must fix."""
    if len(data) > max_mb * 1024 * 1024:
        raise AppError(413, "file_too_large", f"PDFs must be {max_mb} MB or smaller.")
    if b"%PDF-" not in data[:1024]:
        raise AppError(400, "not_a_pdf", "That file isn't a PDF. Please upload a .pdf file.")

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise AppError(400, "not_a_pdf", "This PDF is password-protected. Please upload an unlocked copy.")
        pages = reader.pages
        page_count = len(pages)
    except (PyPdfError, ValueError, KeyError, TypeError, NotImplementedError) as exc:
        logger.info("unreadable PDF: %r", exc)
        raise AppError(400, "not_a_pdf", "That PDF couldn't be read. It may be damaged.") from exc

    if page_count > max_pages:
        raise AppError(413, "file_too_large", f"PDFs must have {max_pages} pages or fewer.")

    texts = [_page_text(page) for page in pages]
    if not any(t.strip() for t in texts):
        raise AppError(
            400,
            "no_text",
            "This PDF has no selectable text. Scanned documents aren't supported.",
        )
    return texts


def _page_text(page) -> str:
    try:
        return page.extract_text() or ""
    except Exception as exc:  # one bad page shouldn't sink the whole document
        logger.info("could not extract a page: %r", exc)
        return ""
