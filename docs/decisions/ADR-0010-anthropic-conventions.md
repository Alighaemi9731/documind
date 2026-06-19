# ADR-0010: Anthropic conventions — official SDK, claude-opus-4-8, adaptive thinking, streaming

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
Where DocuMind calls Anthropic's Claude (for example, an answer-synthesis or evaluation path behind the provider abstraction of ADR-0006), the request shape for the current Opus generation is materially different from older Claude models, and getting it wrong produces hard 400 errors rather than degraded answers. We must pin the model, the thinking mode, the streaming strategy, and explicitly enumerate the parameters that are now rejected, so the adapter is written once and correctly.

## Decision
Use the **official `anthropic` SDK** (not raw HTTP, not an OpenAI-compatible shim), pinned to model **`claude-opus-4-8`**. Enable reasoning with **adaptive thinking** — `thinking={"type": "adaptive"}` — which is the only on-mode for this generation. Default to **streaming** for answer synthesis (long inputs/outputs would otherwise risk request timeouts) and obtain the assembled result via the SDK's **`get_final_message()`** helper rather than hand-assembling stream deltas. Control reasoning depth/cost with `output_config={"effort": ...}`, not a token budget. **Never send `budget_tokens`, `temperature`, `top_p`, or `top_k`** on Opus 4.8 — all four are rejected with **HTTP 400** on this model. Steer behavior through prompting and `effort` instead of sampling parameters.

## Consequences
The adapter targets one known-good request shape, so it cannot regress into a 400 by carrying over a legacy `budget_tokens` or `temperature` parameter. Streaming plus `get_final_message()` gives timeout resilience on long syntheses while still yielding one complete message object to the rest of the pipeline. Tying depth to `effort` rather than a token budget matches the model's actual control surface. Costs: we lose `temperature`-based determinism/variance knobs (must be replaced with prompt-level steering); a future model migration will require revisiting this ADR (the rejected-parameter set and thinking mode are model-generation-specific); the streaming path is slightly more code than a single blocking call.

## Alternatives considered
Raw HTTP or an OpenAI-compatible client shim (loses official SDK helpers like `get_final_message()`, easy to mis-shape requests — rejected). Manual extended thinking with `budget_tokens` (returns HTTP 400 on Opus 4.8 — rejected). Sending `temperature`/`top_p`/`top_k` for output control (all return HTTP 400 on Opus 4.8 — rejected). Non-streaming blocking calls for synthesis (risks HTTP timeouts on long outputs — rejected).
