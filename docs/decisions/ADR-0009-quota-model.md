# ADR-0009: Quota model — atomic pre-call reserve, per-user/day on shared key, global ceiling

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
The operator-funded shared key (ADR-0007) spends real money on every call, so usage on it must be bounded. BYOK users spend their own money and should not be throttled by us. Quota must be enforced before the spend happens (reserving after the call already paid for the tokens) and must hold under concurrent requests without double-spending. The operator also needs a hard ceiling so a single install cannot run away with cost.

## Decision
Enforce an **atomic pre-call reserve**: before issuing a provider call on the shared key, atomically reserve the projected token cost against the user's daily allowance in a single DB statement (so concurrent requests cannot both pass a check-then-spend race). Quota is a **per-user tokens/day** budget (a configurable default) and applies **only to the shared operator key** — **BYOK requests bypass quota entirely**. A **global per-install ceiling** caps total shared-key spend regardless of per-user budgets. Every chargeable call writes a **`usage_events`** row for attribution and reconciliation. When a request would exceed quota, return a **graceful, localized HTTP 429** (a clear, translated message — not a raw error).

## Consequences
Reserving atomically before the call means we never spend tokens we have not accounted for, even under concurrency. Scoping quota to the shared key only keeps BYOK frictionless (their cost, their limit). The global ceiling is a backstop against a compromised or abusive install draining the operator's budget. `usage_events` gives per-user, per-day attribution for billing, debugging, and abuse detection. The localized 429 keeps the multilingual UX coherent. Costs: pre-reserve uses estimated token counts, so actual usage may differ slightly from the reserve (reconciled via `usage_events`); the atomic reserve is a hot path and a potential contention point at high concurrency; quota state is another thing to back up and reason about.

## Alternatives considered
Post-call accounting only (allows overspend and concurrency double-spend before the limit is noticed — rejected). Applying quota to BYOK too (penalizes users for spending their own money — rejected). Per-request rather than per-day limits (poor UX, doesn't bound aggregate cost — rejected). An external rate-limiter/Redis token bucket (extra dependency; the DB-atomic reserve fits the no-Redis-by-default stance of ADR-0005 — rejected for v1).
