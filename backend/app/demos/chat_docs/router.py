import asyncio
import secrets
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from pydantic import BaseModel

from app.core.config import Settings
from app.core.deps import get_llm, get_settings, rate_limited
from app.core.errors import AppError
from app.core.llm import LLMProvider
from app.core.pdf import extract_pages
from app.core.sessions import Session, SessionStore
from app.demos.chat_docs.answer import Citation, build_prompt, parse_citations
from app.demos.chat_docs.chunking import chunk_document
from app.demos.chat_docs.index import ChunkIndex

MAX_QUESTION_CHARS = 1000


class DocumentOut(BaseModel):
    id: str
    name: str
    pages: int
    chunks: int


@dataclass
class ChatState:
    documents: list[DocumentOut] = field(default_factory=list)
    index: ChunkIndex = field(default_factory=ChunkIndex)
    # Serializes uploads and deletes so the document cap can't be raced past
    # while an upload awaits its embeddings.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


ChatSession = Session[ChatState]


class SessionOut(BaseModel):
    session_id: str


class DocumentList(BaseModel):
    documents: list[DocumentOut]


class AskIn(BaseModel):
    question: str = ""


class AskOut(BaseModel):
    answer: str
    citations: list[Citation]


def get_store(request: Request) -> SessionStore[ChatState]:
    return request.app.state.chat_sessions


def get_session(session_id: str, store: SessionStore[ChatState] = Depends(get_store)) -> ChatSession:
    return store.get(session_id)


router = APIRouter(prefix="/api/sessions")


@router.post("", status_code=201, response_model=SessionOut)
async def create_session(store: SessionStore[ChatState] = Depends(get_store)) -> SessionOut:
    return SessionOut(session_id=store.create().id)


@router.post(
    "/{session_id}/documents",
    status_code=201,
    response_model=DocumentOut,
    dependencies=[Depends(rate_limited)],
)
async def upload_document(
    file: UploadFile | None = File(None),
    session: ChatSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    llm: LLMProvider = Depends(get_llm),
) -> DocumentOut:
    if file is None:
        raise AppError(400, "not_a_pdf", "Choose a PDF file to upload.")
    state = session.state
    async with state.lock:
        if len(state.documents) >= settings.max_documents:
            raise AppError(
                409,
                "too_many_documents",
                f"You can upload up to {settings.max_documents} documents. Remove one to add another.",
            )
        data = await file.read(settings.max_file_mb * 1024 * 1024 + 1)
        pages = extract_pages(data, max_mb=settings.max_file_mb, max_pages=settings.max_pages)

        document_id = f"d_{secrets.token_hex(4)}"
        name = file.filename or "document.pdf"
        chunks = chunk_document(document_id, name, pages)
        vectors = await llm.embed([c.text for c in chunks])

        state.index.add(chunks, vectors)
        document = DocumentOut(id=document_id, name=name, pages=len(pages), chunks=len(chunks))
        state.documents.append(document)
        return document


@router.get("/{session_id}/documents", response_model=DocumentList)
async def list_documents(session: ChatSession = Depends(get_session)) -> DocumentList:
    return DocumentList(documents=session.state.documents)


@router.delete("/{session_id}/documents/{document_id}", status_code=204)
async def delete_document(document_id: str, session: ChatSession = Depends(get_session)) -> Response:
    state = session.state
    async with state.lock:
        state.documents = [d for d in state.documents if d.id != document_id]
        state.index.remove_document(document_id)
    return Response(status_code=204)


@router.post("/{session_id}/ask", response_model=AskOut, dependencies=[Depends(rate_limited)])
async def ask(
    body: AskIn,
    session: ChatSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    llm: LLMProvider = Depends(get_llm),
) -> AskOut:
    question = body.question.strip()
    if not question or len(question) > MAX_QUESTION_CHARS:
        raise AppError(
            400,
            "empty_question",
            f"Type a question of up to {MAX_QUESTION_CHARS:,} characters.",
        )
    if not session.state.documents:
        raise AppError(409, "no_documents", "Upload a PDF before asking a question.")

    query = await llm.embed([question])
    sources = session.state.index.search(query[0], settings.top_k)
    system, user = build_prompt(question, sources)
    reply = await llm.complete(system, user)
    answer, citations = parse_citations(reply, sources)
    return AskOut(answer=answer, citations=citations)
