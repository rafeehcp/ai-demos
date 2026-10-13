from app.demos.chat_docs.answer import MAX_QUOTE_CHARS, build_prompt, parse_citations
from app.demos.chat_docs.chunking import Chunk


def sources(n: int) -> list[Chunk]:
    return [Chunk(f"d_{i}", f"doc{i}.pdf", i * 10, f"text of source {i}") for i in range(1, n + 1)]


def test_out_of_range_markers_are_dropped():
    answer, citations = parse_citations("A [1]. B [7]. C [0].", sources(3))
    assert answer == "A [1]. B. C."
    assert [(c.n, c.document_id) for c in citations] == [(1, "d_1")]


def test_renumbers_by_first_mention_and_rewrites_markers():
    answer, citations = parse_citations("First [3]. Second [1]. Again [3]. Both [1, 3].", sources(4))
    assert answer == "First [1]. Second [2]. Again [1]. Both [2][1]."
    assert [(c.n, c.document_id, c.page) for c in citations] == [(1, "d_3", 30), (2, "d_1", 10)]


def test_answer_without_markers_returns_no_citations():
    answer, citations = parse_citations("The documents don't say.", sources(3))
    assert answer == "The documents don't say."
    assert citations == []


def test_quote_is_capped_and_comes_from_the_cited_chunk():
    filler = " ".join(f"filler{i}" for i in range(150))
    text = f"{filler} the tenant may terminate on sixty days notice {filler}"
    chunk = Chunk("d", "lease.pdf", 4, text)
    _, citations = parse_citations("The tenant may terminate on sixty days notice [1].", [chunk])

    quote = citations[0].quote
    assert len(quote) <= MAX_QUOTE_CHARS
    assert "tenant may terminate on sixty days notice" in quote
    assert quote.strip("…") in text


def test_prompt_numbers_sources_with_name_and_page():
    system, user = build_prompt("When?", sources(2))
    assert "[1] doc1.pdf, page 10\ntext of source 1" in user
    assert "[2] doc2.pdf, page 20\ntext of source 2" in user
    assert user.endswith("Question: When?")
    assert "only" in system.lower()
