"""Shared text normalization (ADR-0004) applied identically on ingest + query.

``normalize`` performs, in order:

1. Unicode **NFC** composition.
2. **ZWNJ handling** — collapse runs of zero-width non-joiners and strip
   stray zero-width characters (ZWJ, BOM/ZWNBSP, LRM/RLM marks) that pollute
   keyword matching while keeping a single ZWNJ between joined Persian letters.
3. **Persian/Arabic character folding** — map Arabic Yeh/Kaf/variants and
   Arabic-Indic digits to their Persian/canonical forms, and drop Arabic
   diacritics (harakat) and the tatweel/kashida.
4. Whitespace collapse.

The goal is a single, side-symmetric normalizer so a Persian query with or
without ZWNJ/diacritics matches the same stored ``content_tsv`` tokens.
"""

from __future__ import annotations

import re
import unicodedata

# Zero-width / bidi marks to strip entirely (ZWNJ handled separately).
_ZWNJ = "‌"
_ZERO_WIDTH_STRIP = {
    "​",  # zero-width space
    "‍",  # zero-width joiner
    "‎",  # left-to-right mark
    "‏",  # right-to-left mark
    "﻿",  # BOM / zero-width no-break space
    "­",  # soft hyphen
}

# Arabic -> Persian/canonical character folds.
_CHAR_FOLD = {
    "ي": "ی",  # Arabic Yeh -> Persian Yeh
    "ى": "ی",  # Alef Maksura -> Persian Yeh
    "ك": "ک",  # Arabic Kaf -> Persian Keheh
    "ة": "ه",  # Teh Marbuta -> Heh (common fold)
    "٠": "0",
    "١": "1",
    "٢": "2",
    "٣": "3",
    "٤": "4",
    "٥": "5",
    "٦": "6",
    "٧": "7",
    "٨": "8",
    "٩": "9",
    # Persian (extended Arabic-Indic) digits -> ASCII for stable tokenization.
    "۰": "0",
    "۱": "1",
    "۲": "2",
    "۳": "3",
    "۴": "4",
    "۵": "5",
    "۶": "6",
    "۷": "7",
    "۸": "8",
    "۹": "9",
}

# Arabic diacritics (harakat), superscript alef, and tatweel/kashida to remove.
_DIACRITICS = {
    "ؐ",
    "ؑ",
    "ؒ",
    "ؓ",
    "ؔ",
    "ؕ",
    "ؖ",
    "ؗ",
    "ؘ",
    "ؙ",
    "ؚ",
    "ً",
    "ٌ",
    "ٍ",
    "َ",
    "ُ",
    "ِ",
    "ّ",
    "ْ",
    "ٓ",
    "ٔ",
    "ٕ",
    "ٖ",
    "ٗ",
    "٘",
    "ٰ",  # superscript alef
    "ـ",  # tatweel / kashida
}

_WS_RE = re.compile(r"\s+")
_ZWNJ_RUN_RE = re.compile(_ZWNJ + "+")


def normalize(text: str) -> str:
    """Normalize ``text`` for tsvector generation and query matching.

    Idempotent: ``normalize(normalize(x)) == normalize(x)``.
    """
    if not text:
        return ""

    # 1. NFC composition.
    text = unicodedata.normalize("NFC", text)

    # 2 & 3. Character-level pass: fold, drop diacritics, strip zero-width.
    out_chars: list[str] = []
    for ch in text:
        if ch in _ZERO_WIDTH_STRIP or ch in _DIACRITICS:
            continue
        out_chars.append(_CHAR_FOLD.get(ch, ch))
    text = "".join(out_chars)

    # Collapse ZWNJ runs to a single ZWNJ, then drop ZWNJ adjacent to spaces.
    text = _ZWNJ_RUN_RE.sub(_ZWNJ, text)
    text = text.replace(" " + _ZWNJ, " ").replace(_ZWNJ + " ", " ")

    # 4. Whitespace collapse + trim.
    text = _WS_RE.sub(" ", text).strip()
    return text


__all__ = ["normalize"]
