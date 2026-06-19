"""Token-aware multilingual recursive chunker (ARCHITECTURE.md section 7).

Splits parser :class:`Segment`s into ~``TARGET_TOKENS``-token chunks with
~``OVERLAP_TOKENS`` overlap, using a multilingual boundary cascade
(``\\n\\n`` -> ``\\n`` -> sentence enders incl. Persian ``. ؟ ! ،`` and ZWNJ
awareness -> whitespace -> hard token cut). Splits are always made on Python
``str`` boundaries (code points), so a multibyte character is never bisected.

``text_norm.normalize`` is applied to the chunk content that feeds the tsvector
path so ingest and query agree (ADR-0004). Token counting uses a chars/4
heuristic with a pluggable hook for a provider tokenizer (Gemini ``count_tokens``
in a later phase).

Each emitted :class:`Chunk` carries the resolved citation locators (page_no /
section_path) and the absolute char span back into the source document.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.core.text_norm import normalize
from app.ingestion.parsers import Segment

TARGET_TOKENS = 500
OVERLAP_TOKENS = 60
# Hard ceiling on chunks per document (ARCHITECTURE.md section 7).
MAX_CHUNKS = 10_000

# Heuristic: ~4 characters per token. Overridable via a tokenizer hook.
_CHARS_PER_TOKEN = 4

# Sentence enders: ASCII + Persian/Arabic full stop, question, exclamation,
# Arabic comma. Kept as a character class for the boundary cascade.
_SENTENCE_ENDERS = ".!?؟،؛"
_ZWNJ = "‌"

_PARA_RE = re.compile(r"\n\s*\n")
_SENT_RE = re.compile(r"(?<=[" + re.escape(_SENTENCE_ENDERS) + r"])\s+")
_WS_RE = re.compile(r"\s+")


def default_token_count(text: str) -> int:
    """chars/4 heuristic (rounded up); never returns < 1 for non-empty text."""
    if not text:
        return 0
    return max(1, -(-len(text) // _CHARS_PER_TOKEN))


@dataclass(frozen=True)
class Chunk:
    """A produced chunk ready for embedding + storage."""

    chunk_index: int
    content: str
    # Content after ``text_norm`` — what the tsvector is computed from.
    normalized_content: str
    token_count: int
    char_start: int
    char_end: int
    page_no: int | None = None
    section_path: str | None = None


TokenCounter = Callable[[str], int]


def _split_recursive(text: str, max_tokens: int, token_count: TokenCounter) -> list[str]:
    """Split ``text`` into pieces each <= ``max_tokens``, via the cascade."""
    if token_count(text) <= max_tokens:
        return [text] if text else []

    # 1) paragraph boundaries.
    parts = _PARA_RE.split(text)
    if len(parts) > 1:
        return _merge_and_recurse(parts, max_tokens, token_count, sep="\n\n")

    # 2) line boundaries.
    parts = text.split("\n")
    if len(parts) > 1:
        return _merge_and_recurse(parts, max_tokens, token_count, sep="\n")

    # 3) sentence boundaries (multilingual).
    parts = _SENT_RE.split(text)
    if len(parts) > 1:
        return _merge_and_recurse(parts, max_tokens, token_count, sep=" ")

    # 4) whitespace boundaries (avoid splitting a ZWNJ-joined word).
    parts = _split_on_whitespace(text)
    if len(parts) > 1:
        return _merge_and_recurse(parts, max_tokens, token_count, sep=" ")

    # 5) hard cut on the code-point budget (never mid-codepoint: str slicing).
    return _hard_cut(text, max_tokens)


def _split_on_whitespace(text: str) -> list[str]:
    """Split on whitespace runs but keep ZWNJ-joined sequences intact."""
    return [p for p in _WS_RE.split(text) if p != ""]


def _hard_cut(text: str, max_tokens: int) -> list[str]:
    budget = max(1, max_tokens * _CHARS_PER_TOKEN)
    out: list[str] = []
    for i in range(0, len(text), budget):
        # str slicing operates on code points -> never bisects a character.
        out.append(text[i : i + budget])
    return out


def _merge_and_recurse(
    parts: Sequence[str], max_tokens: int, token_count: TokenCounter, *, sep: str
) -> list[str]:
    """Greedily merge ``parts`` up to ``max_tokens``; recurse oversize parts."""
    out: list[str] = []
    buf = ""
    for part in parts:
        if not part:
            continue
        if token_count(part) > max_tokens:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(_split_recursive(part, max_tokens, token_count))
            continue
        candidate = part if not buf else f"{buf}{sep}{part}"
        if token_count(candidate) > max_tokens:
            out.append(buf)
            buf = part
        else:
            buf = candidate
    if buf:
        out.append(buf)
    return out


def chunk_segments(
    segments: Sequence[Segment],
    *,
    target_tokens: int = TARGET_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
    token_count: TokenCounter = default_token_count,
) -> list[Chunk]:
    """Produce overlapping, token-bounded chunks from parser segments.

    Each segment is split independently so a chunk's page/section locator stays
    accurate (chunks never straddle a page/section boundary). Char offsets are
    resolved back into the absolute document coordinate space.
    """
    chunks: list[Chunk] = []
    index = 0

    for seg in segments:
        text = seg.text
        if not text.strip():
            continue

        pieces = _split_recursive(text, target_tokens, token_count)
        pieces = _apply_overlap(pieces, overlap_tokens, token_count)

        search_from = 0
        for piece in pieces:
            if not piece.strip():
                continue
            # Locate the piece within the segment to get accurate char offsets.
            local = text.find(piece, search_from)
            if local == -1:
                local = text.find(piece)
            if local == -1:
                local = search_from
            char_start = seg.char_start + local
            char_end = char_start + len(piece)
            search_from = local + 1

            chunks.append(
                Chunk(
                    chunk_index=index,
                    content=piece,
                    normalized_content=normalize(piece),
                    token_count=token_count(piece),
                    char_start=char_start,
                    char_end=char_end,
                    page_no=seg.page_no,
                    section_path=seg.section_path,
                )
            )
            index += 1
            if index > MAX_CHUNKS:
                raise _too_many_chunks()
    return chunks


def _apply_overlap(
    pieces: Sequence[str], overlap_tokens: int, token_count: TokenCounter
) -> list[str]:
    """Prepend a token-bounded tail of the previous piece to each piece."""
    if overlap_tokens <= 0 or len(pieces) <= 1:
        return list(pieces)
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN
    out: list[str] = [pieces[0]]
    for prev, cur in zip(pieces, pieces[1:], strict=False):
        tail = prev[-overlap_chars:] if len(prev) > overlap_chars else prev
        # Avoid bisecting a word: trim the tail to the first whitespace.
        space = tail.find(" ")
        if space != -1:
            tail = tail[space + 1 :]
        out.append(f"{tail} {cur}".strip() if tail else cur)
    return out


def _too_many_chunks() -> Exception:
    from app.ingestion.guards import GuardError
    from app.models.enums import DocumentErrorCode

    return GuardError(DocumentErrorCode.TOO_MANY_CHUNKS, "Document produced too many chunks.")


__all__ = [
    "Chunk",
    "chunk_segments",
    "default_token_count",
    "TARGET_TOKENS",
    "OVERLAP_TOKENS",
    "MAX_CHUNKS",
]
