# ADR-0007: Operator-default key location — encrypted DB row seeded from env, admin-rotatable

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
DocuMind offers a shared operator-funded provider key as the fallback when a user has no BYOK key (ADR-0006). The operator must be able to set this key initially and later rotate it (e.g. after a leak or a billing change) without redeploying the stack or editing environment files and restarting containers. The key is a high-value secret and must be encrypted at rest.

## Decision
Store the operator default key in an **`operator_default` database row**, encrypted with **Fernet** using `MASTER_KEY_FERNET`. On first run, if no row exists, seed it from the `OPERATOR_DEFAULT_GEMINI_KEY` environment variable (one-time bootstrap). Thereafter the key is **admin-rotatable through the application** (an authenticated admin endpoint/UI writes a new encrypted value), and the change takes effect immediately for subsequent provider calls — **no redeploy**. The env var is only the seed; the DB row is the source of truth once seeded.

## Consequences
The operator sets the key once via env at install time, then manages rotation in-app, which fits the self-hosted "set it and forget it, fix it without SSH" model and decouples key rotation from container lifecycle. Encryption at rest with the same Fernet master key as BYOK keys keeps one rotation story (runbook: rotate `MASTER_KEY_FERNET` via MultiFernet). Because the DB row wins after first run, changing `OPERATOR_DEFAULT_GEMINI_KEY` in the environment after bootstrap has no effect — this is intentional but must be documented to avoid operator confusion. Costs: the master key now protects DB-resident secrets, so losing `MASTER_KEY_FERNET` means losing the ability to decrypt the operator key (and all BYOK keys); the seed-once semantics need clear messaging.

## Alternatives considered
Read the operator key directly from the environment on every call (no in-app rotation, requires redeploy to change, and the plaintext key sits in the container env — rejected). External secret manager (Vault/SSM) (heavy external dependency, contradicts self-hostable-on-a-VPS goal — rejected for v1). Plaintext DB column (unacceptable at-rest exposure — rejected).
