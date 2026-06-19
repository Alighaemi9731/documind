# ADR-0013: Canonical enums and REST surface — one shared source of truth across subsystems

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
DocuMind spans several subsystems — auth, ingestion, retrieval, providers, quota, the data model, and a TypeScript frontend — built in phases. Without a single canonical definition, the same concept (a document's status, a provider's identity, an error code) drifts: the backend uses one spelling, the frontend another, a migration a third. Drift in enums and in the REST contract is a persistent source of bugs and integration friction across a multi-phase build.

## Decision
Treat **one shared enum set** and **one REST API table** as the **single source of truth** for the whole system; every subsystem (backend models, API handlers, frontend types) derives from them rather than redefining them. The canonical enums are: **`UserRole`, `UserStatus`, `RegistrationMode`, `Provider`, `Capability`, `KeySource`, `DocumentStatus`, `DocumentErrorCode`, `ProviderError`**. The REST surface (paths, methods, request/response shapes, status codes) is likewise defined once and referenced everywhere. Changes to either are deliberate, reviewed contract changes — not incidental edits in one consumer.

## Consequences
The frontend's TypeScript types, the backend's Python enums, and the database's stored values all speak the same vocabulary, so a `DocumentStatus` value means exactly one thing end to end and an exhaustive switch on the frontend stays exhaustive. New phases extend a known contract instead of inventing parallel ones. Reviewing a diff to the enum set or REST table immediately flags a cross-cutting contract change. Costs: contributors must resist the temptation to add an ad-hoc status or error code locally; a change to a canonical enum ripples across subsystems and requires coordinated updates (migrations, frontend types, handlers); the single-source-of-truth discipline must be enforced in review since the language toolchains cannot mechanically guarantee it across Python and TypeScript.

## Alternatives considered
Each subsystem defines its own enums and DTOs (guarantees drift and silent mismatches — rejected). Free-form string statuses/error codes without enums (no compile-time checking, typo-prone — rejected). Auto-generating types from an OpenAPI spec as the only mechanism (valuable but orthogonal; the decision here is that the enum set and REST table are *authoritative* regardless of generation tooling — generation can implement this ADR but does not replace it).
