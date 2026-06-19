"""Prompt-injection neutralization for untrusted chunk text (section 8).

Retrieved chunk text is untrusted data. Two assembly-time defenses live here:

1. :func:`make_nonce` — a per-request random nonce used to build the fence
   delimiters in :mod:`app.rag.prompt`. The model is told never to follow
   instructions inside the fence and to treat the fenced text as data only.
2. :func:`neutralize` — scrubs any string from chunk content that could forge
   the fence or the grounding sentinel: the request nonce itself, generic
   ``<<<GROUNDED...>>>``-like sentinels, and generic ``<<<NONCE_...>>>``-like
   fence markers. A poisoned document therefore cannot close the fence early,
   inject a fake fence, or forge the advisory sentinel.

Neutralization replaces the dangerous markers with a visible, inert placeholder
(so the text still reads naturally) rather than deleting silently.
"""

from __future__ import annotations

import re
import secrets

# Placeholder substituted for any neutralized control-token-like string.
_REDACTED = "[redacted]"

# Generic forms an attacker might embed to forge the fence or the sentinel.
# Matched case-insensitively and independent of the per-request nonce value.
_GROUNDED_LIKE_RE = re.compile(r"<<<\s*GROUNDED\b[^>]*>>>", re.IGNORECASE)
_NONCE_LIKE_RE = re.compile(r"<<<\s*(?:/?\s*)?NONCE[^>]*>>>", re.IGNORECASE)
# Any "<<< ... >>>" delimiter block is fence-shaped; scrub it so a poisoned doc
# cannot inject a delimiter that resembles our random fence at all.
_DELIM_LIKE_RE = re.compile(r"<<<[^>]*>>>")


def make_nonce() -> str:
    """Return a fresh per-request nonce (URL-safe, unguessable)."""
    return secrets.token_hex(16)


def neutralize(content: str, *, nonce: str) -> str:
    """Scrub fence/sentinel-like strings (incl. the live ``nonce``) from content.

    Idempotent and safe on arbitrary text. The live nonce is scrubbed first (in
    case it coincidentally appears), then any sentinel-like or fence-like
    delimiter blocks. Plain prose is unaffected.
    """
    if not content:
        return ""
    out = content
    if nonce:
        out = out.replace(nonce, _REDACTED)
    out = _GROUNDED_LIKE_RE.sub(_REDACTED, out)
    out = _NONCE_LIKE_RE.sub(_REDACTED, out)
    out = _DELIM_LIKE_RE.sub(_REDACTED, out)
    return out


__all__ = ["make_nonce", "neutralize"]
