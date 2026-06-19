"""Grounding gate (ADR-0008) — the raw cosine on the best chunk is THE anchor.

The SOLE trust anchor is the **raw best-chunk cosine similarity** from the vector
leg (NOT the post-RRF score). If ``best_cosine < settings.grounding_min_score``
the request is refused BEFORE any LLM call with a localized refusal (Persian if
the question is Persian, else English).

The model's ``<<<GROUNDED:true|false>>>`` sentinel is ADVISORY and FAIL-CLOSED:
:func:`parse_model_grounded` returns ``True`` only for the single, exact
``true`` sentinel; anything missing / garbled / duplicated / unexpected yields
``False``. The model can never upgrade ``grounded`` false -> true:
:func:`final_grounded` is ``retrieval_ok AND model_grounded``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.core.config import settings
from app.rag.retrieval.vector import VectorHit

# The advisory sentinel the model is asked to emit as its final line.
SENTINEL_PREFIX = "<<<GROUNDED:"
SENTINEL_SUFFIX = ">>>"
SENTINEL_TRUE = "<<<GROUNDED:true>>>"
SENTINEL_FALSE = "<<<GROUNDED:false>>>"

# A single well-formed sentinel anywhere in the text (used to count occurrences).
_SENTINEL_RE = re.compile(r"<<<GROUNDED:(true|false)>>>", re.IGNORECASE)

# Localized refusals (script-matched). Kept short + plain (rendered as markdown).
REFUSAL_EN = "I couldn't find an answer to that in your documents."
REFUSAL_FA = "پاسخ این پرسش در اسناد شما یافت نشد."

# A Persian/Arabic-block code point marks the question as Persian. Ranges:
# Arabic (0600-06FF), Arabic Supplement (0750-077F), Arabic Extended-A
# (08A0-08FF), Presentation Forms-A (FB50-FDFF) and -B (FE70-FEFF).
_PERSIAN_RE = re.compile(
    "[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]"
)


def is_persian(text: str) -> bool:
    """True if the question contains Persian/Arabic-script characters.

    Used only to pick the refusal language; mixed fa/en counts as Persian so a
    Persian speaker gets a Persian refusal.
    """
    return bool(_PERSIAN_RE.search(text))


def refusal_message(question: str) -> str:
    """Return the localized 'not in your documents' refusal for ``question``."""
    return REFUSAL_FA if is_persian(question) else REFUSAL_EN


def best_cosine(vector_hits: Sequence[VectorHit]) -> float | None:
    """The raw cosine similarity of the single closest vector hit, or None.

    The vector leg returns hits ordered by ascending distance, so the first hit
    is the closest; but we take an explicit max to be order-independent.
    """
    if not vector_hits:
        return None
    return max(hit.score_cosine for hit in vector_hits)


def retrieval_grounded(vector_hits: Sequence[VectorHit]) -> bool:
    """Retrieval-side grounding: best raw cosine >= the configured threshold.

    This is computed BEFORE any LLM call; a False result short-circuits to a
    localized refusal and the chat provider is never invoked (ADR-0008).
    """
    score = best_cosine(vector_hits)
    if score is None:
        return False
    return score >= settings.grounding_min_score


def parse_model_grounded(text: str) -> bool:
    """Parse the advisory sentinel, FAIL-CLOSED.

    Returns ``True`` ONLY when exactly one well-formed ``<<<GROUNDED:true>>>``
    sentinel is present (and no ``false`` sentinel). Missing, garbled,
    duplicated, or mixed sentinels -> ``False``. The model can only corroborate
    or downgrade grounding, never manufacture it.
    """
    matches = _SENTINEL_RE.findall(text or "")
    if len(matches) != 1:
        # Missing or duplicated -> fail closed.
        return False
    return matches[0].lower() == "true"


def final_grounded(*, retrieval_ok: bool, model_grounded: bool) -> bool:
    """Authoritative grounded value = retrieval_ok AND model_grounded (ADR-0008)."""
    return retrieval_ok and model_grounded


__all__ = [
    "SENTINEL_PREFIX",
    "SENTINEL_SUFFIX",
    "SENTINEL_TRUE",
    "SENTINEL_FALSE",
    "REFUSAL_EN",
    "REFUSAL_FA",
    "is_persian",
    "refusal_message",
    "best_cosine",
    "retrieval_grounded",
    "parse_model_grounded",
    "final_grounded",
]
