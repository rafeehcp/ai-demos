import re
from dataclasses import dataclass

from app.demos.chat_docs.chunking import Chunk

MAX_QUOTE_CHARS = 300

SYSTEM_PROMPT = """You answer questions about the user's documents.
Use only the numbered sources provided. Do not use outside knowledge.
Cite every claim with the number of its source in square brackets, like [1] or [2].
If the sources do not answer the question, say plainly that the documents don't say, and cite nothing.
Keep the answer short and direct."""

# Matches "[3]" and grouped forms like "[1, 3]", plus the whitespace before them,
# so a dropped marker doesn't leave a stray space.
_MARKER = re.compile(r"(\s*)\[(\d+(?:\s*,\s*\d+)*)\]")
_WORD = re.compile(r"\w{3,}")


@dataclass(frozen=True)
class Citation:
    n: int
    document_id: str
    document_name: str
    page: int
    quote: str


def build_prompt(question: str, sources: list[Chunk]) -> tuple[str, str]:
    blocks = [
        f"[{i}] {c.document_name}, page {c.page}\n{c.text}"
        for i, c in enumerate(sources, start=1)
    ]
    user = "Sources:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"
    return SYSTEM_PROMPT, user


def parse_citations(answer: str, sources: list[Chunk]) -> tuple[str, list[Citation]]:
    """Drop markers outside 1..len(sources), renumber the rest by first mention,
    and return the rewritten answer with the cited sources."""
    renumbered: dict[int, int] = {}
    first_context: dict[int, str] = {}

    def rewrite(match: re.Match) -> str:
        new_numbers: list[int] = []
        for raw in re.findall(r"\d+", match.group(2)):
            original = int(raw)
            if not 1 <= original <= len(sources):
                continue
            if original not in renumbered:
                renumbered[original] = len(renumbered) + 1
                first_context[original] = answer[max(0, match.start() - MAX_QUOTE_CHARS) : match.start()]
            if renumbered[original] not in new_numbers:
                new_numbers.append(renumbered[original])
        if not new_numbers:
            return ""
        return match.group(1) + "".join(f"[{n}]" for n in new_numbers)

    text = _MARKER.sub(rewrite, answer).strip()
    citations = [
        Citation(
            n=n,
            document_id=sources[original - 1].document_id,
            document_name=sources[original - 1].document_name,
            page=sources[original - 1].page,
            quote=best_quote(sources[original - 1].text, first_context[original]),
        )
        for original, n in renumbered.items()
    ]
    return text, citations


def best_quote(text: str, context: str, limit: int = MAX_QUOTE_CHARS) -> str:
    """The excerpt of `text` (at most `limit` chars, ellipses included) sharing
    the most words with `context`, the answer text that cites it."""
    if len(text) <= limit:
        return text
    words = text.split()
    wanted = {w.lower() for w in _WORD.findall(context)}
    budget = limit - 2  # room for a leading and trailing ellipsis
    best_start, best_end, best_score = 0, 0, -1
    for start in range(len(words)):
        end, length = start, -1
        while end < len(words) and length + 1 + len(words[end]) <= budget:
            length += 1 + len(words[end])
            end += 1
        if end == start:
            continue
        score = len(wanted & {w.lower() for w in _WORD.findall(" ".join(words[start:end]))})
        if score > best_score:
            best_start, best_end, best_score = start, end, score
        if end == len(words):
            break
    if best_end == 0:
        return text[: limit - 1] + "…"
    excerpt = " ".join(words[best_start:best_end])
    prefix = "…" if best_start > 0 else ""
    suffix = "…" if best_end < len(words) else ""
    return prefix + excerpt + suffix
