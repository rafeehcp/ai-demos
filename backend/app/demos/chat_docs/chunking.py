from dataclasses import dataclass

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


@dataclass(frozen=True)
class Chunk:
    document_id: str
    document_name: str
    page: int  # 1-based
    text: str


def chunk_document(
    document_id: str,
    document_name: str,
    pages: list[str],
    *,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    return [
        Chunk(document_id, document_name, page_number, text)
        for page_number, page_text in enumerate(pages, start=1)
        for text in split_text(page_text, size=size, overlap=overlap)
    ]


def split_text(text: str, *, size: int, overlap: int) -> list[str]:
    """Whitespace-split windows of at most `size` chars; each window after the
    first starts with up to `overlap` chars of trailing words from the previous one."""
    words = [piece for word in text.split() for piece in _pieces(word, size)]
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        if current and length + 1 + len(word) > size:
            chunks.append(" ".join(current))
            current = _tail(current, overlap)
            length = len(" ".join(current))
            if current and length + 1 + len(word) > size:
                current, length = [], 0
        length += len(word) + (1 if current else 0)
        current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _pieces(word: str, size: int) -> list[str]:
    return [word[i : i + size] for i in range(0, len(word), size)]


def _tail(words: list[str], overlap: int) -> list[str]:
    tail: list[str] = []
    length = -1
    for word in reversed(words):
        length += len(word) + 1
        if length > overlap:
            break
        tail.append(word)
    return tail[::-1]
