"""RAG core (ARCHITECTURE.md section 8) — hybrid retrieval + grounded answers.

Submodules:

- ``retrieval/`` — vector (pgvector cosine), keyword (tsvector), RRF fusion, rerank.
- ``grounding`` — the raw-cosine grounding gate (sole trust anchor, ADR-0008).
- ``budget`` / ``prompt`` / ``injection`` — nonce-fenced, injection-resistant prompt.
- ``answer`` — provider streaming, sentinel stripping, citation validation, SSE.

Everything imports without a live DB so unit tests run offline.
"""

from __future__ import annotations

__all__: list[str] = []
