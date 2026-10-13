from app.demos.chat_docs.chunking import chunk_document, split_text


def test_each_chunk_keeps_its_page_and_never_merges_pages():
    pages = ["alpha " * 10, "", "bravo " * 400, "charlie delta"]
    chunks = chunk_document("d_1", "a.pdf", pages)

    expected_words = {1: {"alpha"}, 3: {"bravo"}, 4: {"charlie", "delta"}}
    assert {c.page for c in chunks} == set(expected_words)
    for chunk in chunks:
        assert set(chunk.text.split()) == expected_words[chunk.page]
    assert sum(c.page == 3 for c in chunks) > 1
    assert all(c.document_id == "d_1" and c.document_name == "a.pdf" for c in chunks)


def test_short_pages_are_not_combined_even_when_they_would_fit():
    chunks = chunk_document("d", "n", ["one", "two", "three"])
    assert [(c.page, c.text) for c in chunks] == [(1, "one"), (2, "two"), (3, "three")]


def test_chunks_respect_size_and_overlap_previous_chunk():
    words = [f"w{i:03d}" for i in range(600)]
    chunks = split_text(" ".join(words), size=1000, overlap=150)

    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)
    for previous, current in zip(chunks, chunks[1:]):
        prev_words, cur_words = previous.split(), current.split()
        shared = [w for w in cur_words if w in prev_words]
        assert shared, "consecutive chunks share overlapping words"
        assert cur_words[: len(shared)] == prev_words[-len(shared) :]
        assert len(" ".join(shared)) <= 150
        assert len(" ".join(shared)) >= 150 - 5
    covered = [w for c in chunks for w in c.split()]
    assert set(covered) == set(words)
    assert covered[-1] == words[-1]


def test_word_longer_than_chunk_size_is_split_and_text_is_preserved():
    long_word = "x" * 2500
    chunks = split_text(f"start {long_word} end", size=1000, overlap=150)
    assert all(len(c) <= 1000 for c in chunks)
    assert "".join(chunks).count("x") >= 2500
    assert chunks[0].startswith("start") and chunks[-1].endswith("end")
