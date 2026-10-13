from typing import Optional

import numpy as np

from app.demos.chat_docs.chunking import Chunk


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.where(norms == 0, 1.0, norms)


class ChunkIndex:
    """Chunks plus one L2-normalized float32 row per chunk; search is cosine similarity."""

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.vectors: Optional[np.ndarray] = None

    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
        rows = _normalize(np.asarray(vectors, dtype=np.float32))
        self.vectors = rows if self.vectors is None else np.vstack([self.vectors, rows])
        self.chunks.extend(chunks)

    def remove_document(self, document_id: str) -> None:
        keep = [i for i, c in enumerate(self.chunks) if c.document_id != document_id]
        self.chunks = [self.chunks[i] for i in keep]
        self.vectors = self.vectors[keep] if self.vectors is not None and keep else None

    def search(self, query: np.ndarray, k: int) -> list[Chunk]:
        if self.vectors is None or not self.chunks:
            return []
        scores = self.vectors @ _normalize(np.asarray(query, dtype=np.float32).ravel())
        top = np.argsort(-scores, kind="stable")[:k]
        return [self.chunks[i] for i in top]
