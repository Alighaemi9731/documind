# ADR-0016: No SMTP in v1 — copyable invite links and in-app pending state instead of email

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
Two common flows usually rely on email: inviting a new user, and notifying an admin that a registration is awaiting approval (relevant when `REGISTRATION_MODE` is set to an approval mode rather than the default `open`). Shipping email means configuring SMTP credentials, handling deliverability, bounces, and spam filtering — a significant operational burden for a self-hosted product whose operator may not have a working mail relay at all. For v1 we want zero external email dependencies.

## Decision
**No email subsystem in v1.** Invites are delivered as a **copyable link** that the application generates and the **operator relays** out-of-band (chat, existing email, etc.) — DocuMind never sends mail. The approval flow is handled **in-app, not by notification**: a user whose registration awaits approval sees a **persistent "pending" state on login**, and the **admin sees a pending-count badge** in the UI to know there is something to act on. SMTP is explicitly deferred as a **documented post-v1 extension**, not a hidden gap.

## Consequences
A fresh install works with no mail configuration whatsoever, which removes the single most common self-hosting setup failure (broken/absent SMTP) and keeps the install story simple (ADR-0011). Invite-by-copyable-link and in-app pending state are fully functional without any outbound network mail. The admin badge plus the user's pending screen close the approval loop using only in-app signals. Costs: invites require a manual relay step by the operator (no automated "you've been invited" email); approval is pull-based (the admin must look at the badge) rather than push-based (no email alert), so time-to-approval depends on the admin checking the UI. These trade-offs are acceptable for v1 and are removed cleanly if the post-v1 SMTP extension is added.

## Alternatives considered
Bundle an SMTP client and require operator mail config (highest-friction setup step, frequent breakage on self-hosted boxes — rejected for v1). Use a third-party transactional email API (external dependency, API key management, cost — contradicts self-hostable-with-no-external-services goal — rejected). Auto-approve all registrations to avoid the notification problem (loses the approval gate operators may want — rejected; in-app pending state chosen instead).
