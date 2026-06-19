# ADR-0004: Keyword search and multilingual normalization — simple tsvector plus shared text_norm

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
Hybrid retrieval pairs dense vectors (ADR-0003) with lexical search. DocuMind must serve multilingual corpora, notably Persian/Arabic-script text, where the same word appears with and without ZWNJ (zero-width non-joiner), with Arabic vs Persian forms of the same letter (e.g. `ي`/`ی`, `ك`/`ک`), and in mixed Unicode normalization forms. If ingest and query normalize text differently, a chunk that contains a term will fail to match a query for that same term. Postgres language-specific stemming dictionaries do not cover Persian well and can mangle other languages.

## Decision
Use a `tsvector` built with the **`simple`** configuration (no language stemming, no stopword removal), stored as a `GENERATED ... STORED` column and indexed with **GIN**, complemented by **`pg_trgm`** for fuzzy/substring matching. The lexical match quality comes not from a stemmer but from **one shared `text_norm` function** — NFC Unicode normalization, ZWNJ handling, and Persian/Arabic character folding — applied **identically on both ingest and query**. Because the same normalization runs on both sides, we deliberately reject any one-sided transform such as applying `unaccent` only at query time.

## Consequences
A term indexed at ingest is found by the same term at query time, in any of the languages we target, because both passed through the identical `text_norm`. The `simple` config avoids language-detection complexity and Persian-hostile stemming. `pg_trgm` covers typo tolerance and partial matches that exact lexeme matching misses. The generated-stored column keeps the tsvector in sync automatically. Costs: `simple` means no stemming, so morphological variants (plurals, conjugations) do not collapse — partially mitigated by trigram matching and by dense retrieval; `text_norm` becomes a shared dependency that must be byte-for-byte consistent across the ingest and query paths or matching silently degrades.

## Alternatives considered
Language-specific tsvector configs with stemming (poor Persian support, requires reliable per-chunk language detection — rejected). One-sided `unaccent`/normalization at query time only (asymmetry causes silent misses — explicitly rejected). External search engine (Elasticsearch/Meilisearch) (extra service, contradicts the lean single-VPS deployment and the swapfile-on-2GB target — rejected for v1).
