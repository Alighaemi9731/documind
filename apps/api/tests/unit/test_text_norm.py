"""Unit tests for the shared text normalizer (ADR-0004)."""

from __future__ import annotations

import unicodedata

from app.core.text_norm import normalize


def test_empty_and_whitespace() -> None:
    assert normalize("") == ""
    assert normalize("   ") == ""
    assert normalize("a\t\n  b") == "a b"


def test_nfc_composition() -> None:
    # Decomposed 'é' (e + combining acute) -> composed single codepoint.
    decomposed = "é"
    assert normalize(decomposed) == unicodedata.normalize("NFC", decomposed)
    assert len(normalize(decomposed)) == 1


def test_arabic_yeh_and_kaf_fold_to_persian() -> None:
    # Arabic Yeh (ي) -> Persian Yeh (ی); Arabic Kaf (ك) -> ک.
    arabic = "يك"
    persian = "یک"
    assert normalize(arabic) == persian
    # Idempotent on already-Persian text.
    assert normalize(persian) == persian


def test_arabic_indic_and_persian_digits_fold_to_ascii() -> None:
    assert normalize("١٢٣") == "123"  # Arabic-Indic
    assert normalize("۱۲۳") == "123"  # Persian digits


def test_diacritics_are_stripped() -> None:
    # 'مَدْرَسَه' with harakat normalizes to the bare letters.
    with_harakat = "مَدْرَسَه"
    without = "مدرسه"
    assert normalize(with_harakat) == without


def test_tatweel_is_removed() -> None:
    assert normalize("سلــام") == "سلام"


def test_zwnj_runs_collapse_and_strip_around_space() -> None:
    zwnj = "‌"
    # A run of ZWNJ collapses to one; ZWNJ next to a space disappears.
    assert normalize(f"a{zwnj}{zwnj}b") == f"a{zwnj}b"
    assert normalize(f"a {zwnj}b") == "a b"
    assert normalize(f"a{zwnj} b") == "a b"


def test_zero_width_marks_are_stripped() -> None:
    polluted = "a​b‎‏c﻿"
    assert normalize(polluted) == "abc"


def test_normalize_is_idempotent() -> None:
    samples = [
        "Hello World",
        "يكــ ١٢",
        "é‌‌test",
        "مَدرسه",
    ]
    for s in samples:
        once = normalize(s)
        assert normalize(once) == once
