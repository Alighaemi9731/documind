"""Server-side sentinel stripping for the token stream (ADR-0008).

The model is asked to end with a ``<<<GROUNDED:true|false>>>`` sentinel. The
sentinel is server state, never client state: the literal sentinel must NEVER
reach the client. :class:`SentinelStripper` is a bounded-lookahead streaming
filter that removes EVERY ``<<<GROUNDED:...>>>`` occurrence — at EOF, mid-text
(a forged sentinel inside the body), and split across arbitrary token
boundaries — while emitting all other text unchanged and without unbounded
buffering.

Algorithm: buffer only a bounded tail that could be the start of a sentinel.
On each ``feed`` we scan for complete sentinels (removing them and recording
their value), then hold back the longest suffix that is a prefix of the sentinel
opener so a sentinel split across chunks is caught on the next feed. ``flush``
emits whatever harmless tail remains (a partial sentinel at EOF is dropped, since
an incomplete ``<<<GROUNDED`` prefix is never legitimate output).
"""

from __future__ import annotations

import re

_SENTINEL_RE = re.compile(r"<<<GROUNDED:(true|false)>>>", re.IGNORECASE)
# The opener we hold back a partial match for. Max sentinel length bounds buffer.
_OPENER = "<<<GROUNDED:"
_OPENER_LOWER = _OPENER.lower()  # comparisons below are case-insensitive
_MAX_SENTINEL_LEN = len("<<<GROUNDED:false>>>")


def _longest_suffix_that_is_sentinel_prefix(buf: str) -> int:
    """Length of the longest suffix of ``buf`` that could begin a sentinel.

    We only need to hold back a suffix that is a prefix of a *potential*
    sentinel. A suffix qualifies if it starts a ``<<<GROUNDED:...`` token: it is
    a prefix of ``<<<GROUNDED:`` itself, or it is ``<<<GROUNDED:`` plus an
    in-progress ``true``/``false`` (possibly with a partial ``>>>``). We bound
    the scan to the max sentinel length.
    """
    max_keep = min(len(buf), _MAX_SENTINEL_LEN - 1)
    for keep in range(max_keep, 0, -1):
        suffix = buf[len(buf) - keep :]
        if _could_be_sentinel_prefix(suffix):
            return keep
    return 0


def _could_be_sentinel_prefix(s: str) -> bool:
    """True if ``s`` is a viable in-progress prefix of a GROUNDED sentinel."""
    lower = s.lower()
    # Case 1: still inside the opener "<<<grounded:".
    if len(lower) <= len(_OPENER_LOWER):
        return _OPENER_LOWER.startswith(lower)
    # Case 2: opener complete; the remainder must be a prefix of
    # "true>>>" or "false>>>".
    if not lower.startswith(_OPENER_LOWER):
        return False
    rest = lower[len(_OPENER_LOWER) :]
    return "true>>>".startswith(rest) or "false>>>".startswith(rest)


class SentinelStripper:
    """Streaming filter that removes every GROUNDED sentinel from a token stream.

    Usage:
        stripper = SentinelStripper()
        for token in stream:
            safe = stripper.feed(token)   # emit `safe` to the client
        tail = stripper.flush()           # emit final tail
        grounded = stripper.model_grounded  # last sentinel value, fail-closed
    """

    def __init__(self) -> None:
        self._buf = ""
        # How many well-formed sentinels we removed, and the last value seen.
        self.sentinel_count = 0
        self._last_value: bool | None = None

    def feed(self, text: str) -> str:
        """Consume a token; return the text safe to emit to the client now."""
        if not text:
            return ""
        self._buf += text

        # Remove every complete sentinel from the buffer, recording values.
        emitted_parts: list[str] = []
        while True:
            match = _SENTINEL_RE.search(self._buf)
            if match is None:
                break
            # Everything before the sentinel is safe to emit (modulo the held
            # tail, handled below). Keep the post-match remainder in the buffer.
            emitted_parts.append(self._buf[: match.start()])
            self.sentinel_count += 1
            self._last_value = match.group(1).lower() == "true"
            self._buf = self._buf[match.end() :]

        safe_prefix = "".join(emitted_parts)

        # From the residual buffer, hold back only a possible sentinel-prefix
        # tail; emit the rest now.
        keep = _longest_suffix_that_is_sentinel_prefix(self._buf)
        flushable = self._buf[: len(self._buf) - keep]
        self._buf = self._buf[len(self._buf) - keep :]
        return safe_prefix + flushable

    def flush(self) -> str:
        """End of stream: emit any harmless tail; drop a partial sentinel.

        A residual buffer that is a viable sentinel prefix (e.g. ``<<<GROUNDED``
        at EOF) is dropped — an incomplete sentinel is never legitimate output.
        Otherwise the residual is real text and is emitted.
        """
        residual = self._buf
        self._buf = ""
        if residual and _could_be_sentinel_prefix(residual):
            return ""
        return residual

    @property
    def model_grounded(self) -> bool:
        """Fail-closed grounding from the sentinel stream.

        True ONLY when exactly one well-formed sentinel was seen and it was
        ``true``. Missing or duplicated sentinels -> False (ADR-0008).
        """
        if self.sentinel_count != 1:
            return False
        return self._last_value is True


__all__ = ["SentinelStripper"]
