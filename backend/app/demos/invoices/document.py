import base64
import io
import logging
from dataclasses import dataclass

import pypdfium2 as pdfium
from PIL import Image, ImageOps

from app.core.errors import AppError
from app.core.pdf import read_pages

logger = logging.getLogger(__name__)

# Long edge in pixels. Enough for small print on an A4 page; larger only costs tokens.
PAGE_PIXELS = 1600
PHOTO_PIXELS = 2000
# A 10 MB JPEG can decode to far more pixels than any phone takes.
MAX_SOURCE_PIXELS = 50_000_000

_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}
_UNSUPPORTED = "Upload a PDF, PNG, JPEG or WebP file."


@dataclass(frozen=True)
class Document:
    """One upload, ready for the model: the text layer per page (empty for photos
    and scans) and one image per page as a data URL."""

    texts: list[str]
    images: list[str]

    @property
    def has_text(self) -> bool:
        return any(t.strip() for t in self.texts)


def read_document(data: bytes, *, max_mb: int, max_pages: int) -> Document:
    if len(data) > max_mb * 1024 * 1024:
        raise AppError(413, "file_too_large", f"Files must be {max_mb} MB or smaller.")
    if b"%PDF-" in data[:1024]:
        return _read_pdf(data, max_mb=max_mb, max_pages=max_pages)
    if _looks_like_image(data):
        return Document(texts=[], images=[_photo_data_url(data)])
    raise AppError(400, "unsupported_file", f"That file type isn't supported. {_UNSUPPORTED}")


def _looks_like_image(data: bytes) -> bool:
    return (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    )


def _read_pdf(data: bytes, *, max_mb: int, max_pages: int) -> Document:
    texts = read_pages(data, max_mb=max_mb, max_pages=max_pages)
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        logger.info("pdfium could not open a PDF that pypdf read: %r", exc)
        raise AppError(400, "not_a_pdf", "That PDF couldn't be read. It may be damaged.") from exc
    try:
        images = []
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                width, height = page.get_size()
                bitmap = page.render(scale=PAGE_PIXELS / max(width, height, 1))
                images.append(_data_url(bitmap.to_pil(), "PNG"))
            finally:
                page.close()
    finally:
        pdf.close()
    return Document(texts=texts, images=images)


def _photo_data_url(data: bytes) -> str:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in _IMAGE_FORMATS:
                raise AppError(400, "unsupported_file", f"That image type isn't supported. {_UNSUPPORTED}")
            if image.width * image.height > MAX_SOURCE_PIXELS:
                raise AppError(413, "file_too_large", "That image is too large. Please upload a smaller photo.")
            # Phones store rotation as an EXIF tag; the model sees raw pixels.
            upright = ImageOps.exif_transpose(image).convert("RGB")
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        logger.info("unreadable image: %r", exc)
        raise AppError(400, "unsupported_file", "That image couldn't be read. It may be damaged.") from exc
    upright.thumbnail((PHOTO_PIXELS, PHOTO_PIXELS))
    return _data_url(upright, "JPEG")


def _data_url(image: Image.Image, fmt: str) -> str:
    buffer = io.BytesIO()
    image.save(buffer, fmt, quality=90)
    return f"data:image/{fmt.lower()};base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}"
