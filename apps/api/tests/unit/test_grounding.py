"""Grounding gate: language selection, threshold, sentinel fail-closed (ADR-0008)."""

from __future__ import annotations

import uuid

from app.core.config import settings
from app.rag import grounding
from app.rag.retrieval.vector import VectorHit


def _vhit(score: float) -> VectorHit:
    return VectorHit(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="f.txt",
        page_no=None,
        section_path=None,
        chunk_index=0,
        content="c",
        score_cosine=score,
    )


def test_refusal_language_persian() -> None:
    assert grounding.is_persian("سرفصل قرارداد چیست؟")
    assert grounding.refusal_message("سرفصل قرارداد چیست؟") == grounding.REFUSAL_FA


def test_refusal_language_english() -> None:
    assert not grounding.is_persian("What is the contract term?")
    assert grounding.refusal_message("What is the contract term?") == grounding.REFUSAL_EN


def test_mixed_script_counts_as_persian() -> None:
    # A mostly-English question with a Persian word still gets a Persian refusal.
    assert grounding.refusal_message("Define واژه here") == grounding.REFUSAL_FA


def test_best_cosine_takes_max() -> None:
    assert grounding.best_cosine([_vhit(0.3), _vhit(0.71), _vhit(0.5)]) == 0.71
    assert grounding.best_cosine([]) is None


def test_retrieval_grounded_threshold() -> None:
    thr = settings.grounding_min_score
    assert grounding.retrieval_grounded([_vhit(thr + 0.01)]) is True
    assert grounding.retrieval_grounded([_vhit(thr - 0.01)]) is False
    assert grounding.retrieval_grounded([]) is False


def test_parse_model_grounded_fail_closed() -> None:
    assert grounding.parse_model_grounded("answer <<<GROUNDED:true>>>") is True
    assert grounding.parse_model_grounded("answer <<<GROUNDED:false>>>") is False
    # Missing.
    assert grounding.parse_model_grounded("answer with no sentinel") is False
    # Duplicated -> fail closed.
    assert grounding.parse_model_grounded("<<<GROUNDED:true>>> <<<GROUNDED:true>>>") is False
    # Garbled.
    assert grounding.parse_model_grounded("<<<GROUNDED: maybe >>>") is False


def test_final_grounded_model_cannot_upgrade() -> None:
    # retrieval False can never be rescued by the model claiming true.
    assert grounding.final_grounded(retrieval_ok=False, model_grounded=True) is False
    # retrieval True + model false -> downgraded.
    assert grounding.final_grounded(retrieval_ok=True, model_grounded=False) is False
    # Both true -> grounded.
    assert grounding.final_grounded(retrieval_ok=True, model_grounded=True) is True
