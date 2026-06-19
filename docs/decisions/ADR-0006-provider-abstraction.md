# ADR-0006: Provider abstraction and resolution — narrow Protocols, lazy registry, two-tier BYOK resolver

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
DocuMind calls external LLM and embedding providers. We want to support multiple providers over time, let users bring their own keys (BYOK) while also offering an operator-funded shared default, store keys encrypted at rest, and never let a misconfigured or attacker-supplied "base URL" turn a provider call into a server-side request forgery (SSRF) against internal infrastructure. Adding a provider should be a small, contained change.

## Decision
Two **narrow Python Protocols** define the surface: `LLMProvider` and `EmbeddingProvider` (just the methods the app needs). A **static, lazy-import registry** maps provider enum values to adapter modules, importing an adapter only when first used. A **per-capability two-tier resolver** picks the key for a given capability (LLM vs embedding): first a user's BYOK key, falling back to the **shared operator default** (ADR-0007). Keys are encrypted at rest with **Fernet/MultiFernet** (`MASTER_KEY_FERNET`), and in-process they are carried in a **redacting `Secret` type** whose `repr`/`str`/log serialization never reveals the value. Provider **base URLs are hard-coded** per adapter — never taken from user input — to eliminate SSRF. The design goal is literally: **"adding a provider = writing one adapter file."**

## Consequences
Swapping or adding a provider is isolated to a single adapter implementing the Protocol plus a registry entry; nothing else in the app changes. Lazy import keeps unused provider SDKs out of memory (relevant on small hosts). The two-tier resolver makes BYOK-vs-shared a single, testable decision point. The redacting `Secret` type prevents the most common key-leak vector (accidental logging). Hard-coded base URLs close the SSRF hole at the cost of flexibility — pointing an adapter at a proxy or self-hosted gateway requires a code change, not config. Costs: Protocols give structural typing but no runtime enforcement of behavior; MultiFernet key rotation requires operational discipline (ADR-0007, runbook).

## Alternatives considered
A single fat provider interface (forces every adapter to implement irrelevant methods — rejected). LangChain or a similar framework abstraction (heavy dependency, opaque control flow, hard to audit for key handling and SSRF — rejected). Config-driven base URLs (reintroduces SSRF — explicitly rejected). Storing keys in plaintext or env-only (no per-user BYOK, no rotation — rejected).
