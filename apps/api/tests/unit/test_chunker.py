"""Chunker unit tests: token cap, overlap, ZWNJ, no mid-codepoint, Persian."""

from __future__ import annotations

from app.ingestion.chunker import (
    OVERLAP_TOKENS,
    TARGET_TOKENS,
    chunk_segments,
    default_token_count,
)
from app.ingestion.parsers import Segment

ZWNJ = "‌"


def _seg(text: str) -> Segment:
    return Segment(text=text, char_start=0, char_end=len(text))


def test_token_cap_respected() -> None:
    # Build a long English document well over the target token budget.
    text = " ".join(f"word{i}" for i in range(4000))
    chunks = chunk_segments([_seg(text)])
    assert len(chunks) > 1
    # No chunk wildly exceeds the cap (overlap adds a bounded prefix).
    for c in chunks:
        assert c.token_count <= TARGET_TOKENS + OVERLAP_TOKENS + 5


def test_overlap_present_between_consecutive_chunks() -> None:
    text = " ".join(f"token{i}" for i in range(3000))
    chunks = chunk_segments([_seg(text)])
    assert len(chunks) >= 2
    # The overlap means the start of a later chunk repeats tail content of the
    # previous one for at least one shared token.
    prev_tail_tokens = set(chunks[0].content.split()[-OVERLAP_TOKENS:])
    next_head_tokens = set(chunks[1].content.split()[:OVERLAP_TOKENS])
    assert prev_tail_tokens & next_head_tokens


def test_never_splits_mid_codepoint() -> None:
    # A run of multibyte emoji + Persian, no whitespace, forcing a hard cut.
    text = ("😀" * 1500) + ("سلام" * 1500)
    chunks = chunk_segments([_seg(text)])
    # Re-joining every chunk's content must reconstruct valid code points
    # (str slicing guarantees this; assert each chunk encodes cleanly).
    for c in chunks:
        c.content.encode("utf-8")  # would raise on a lone surrogate
        assert "�" not in c.content


def test_persian_sentence_boundaries() -> None:
    # Persian sentences separated by Persian punctuation should be splittable.
    sentence = "این یک جمله نمونه فارسی است؟ "
    text = sentence * 400  # large enough to require splitting
    chunks = chunk_segments([_seg(text)])
    assert len(chunks) > 1
    # The Persian question mark must survive into chunk content.
    assert any("؟" in c.content for c in chunks)


def test_zwnj_preserved_in_content() -> None:
    word = f"می{ZWNJ}رود"
    text = (word + " ") * 5
    chunks = chunk_segments([_seg(text)])
    assert chunks
    # The normalized content path keeps a single ZWNJ between joined letters.
    assert any(ZWNJ in c.normalized_content for c in chunks)


def test_char_offsets_within_segment() -> None:
    text = " ".join(f"w{i}" for i in range(2000))
    seg = Segment(text=text, char_start=100, char_end=100 + len(text), page_no=3)
    chunks = chunk_segments([seg])
    for c in chunks:
        assert c.char_start >= 100
        assert c.char_end <= 100 + len(text)
        assert c.page_no == 3


def test_token_count_heuristic() -> None:
    assert default_token_count("") == 0
    assert default_token_count("abcd") == 1
    assert default_token_count("a" * 400) == 100
