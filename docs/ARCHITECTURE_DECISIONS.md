# Stage 1 Architecture Decisions

## ADR-001 - Operational Truth Boundary

- Status: accepted
- Decision: BuenPick Internal API is the only operational source of truth.
- Rationale: availability rules, price, stock, commerce, pickup, orders, ownership, media URLs, and purchase URLs already belong to BuenPick.
- Consequence: Piki cannot scrape, query BuenPick's database, or reconstruct these rules locally.

## ADR-002 - Typed Tool Boundary

- Status: accepted
- Decision: tools are typed application ports returning a common result envelope; they do not author or send user messages.
- Consequence: regex tags and legacy tool notifications are not migrated. Initial tools are search pick, get pick, get commerce, get owned order, prepare pick image, and request handoff.

## ADR-003 - Evidence-First Composition

- Status: accepted
- Decision: policy and tools build a typed `ContextPacket`; Jinja renders an evidence packet; the LLM optionally turns that evidence into Piki's voice; grounding validates the result before delivery.
- Consequence: commercial paths cannot use an evidence-free LLM mode.

## ADR-004 - Jinja Is Not Knowledge

- Status: accepted
- Decision: templates contain structure and writing constraints only.
- Consequence: changing products, prices, stock, commerce, schedules, real examples, credentials, and tool results are prohibited in template source.

## ADR-005 - Explicit Response Modes

- Status: accepted
- Decision: policies select among deterministic, Jinja-only, Jinja+LLM, and non-commercial LLM modes.
- Consequence: stock, price, orders, ownership, pickup, public URL, and delivery status never use pure LLM generation.

## ADR-006 - State Ownership

- Status: accepted
- Decision: Redis owns ephemeral state, deduplication, locks, pending actions, and active pick; PostgreSQL owns durable conversations, messages, tool runs, delivery attempts/statuses, handoffs, traces, and evaluations.
- Consequence: no global DB sessions. Keys include channel/account/conversation identity and TTL. Safe degradation must never cross conversations.

## ADR-007 - Active Pick Reconfirmation

- Status: accepted
- Decision: active pick stores identity/context, not authoritative availability. Operational facts are reconfirmed through BuenPick before use.
- Consequence: expired or `404` picks are invalidated; media requests cannot rely on local filenames.

## ADR-008 - pgvector Is Candidate Retrieval

- Status: accepted
- Decision: PostgreSQL + pgvector is the only vector engine, with separate catalog, stable knowledge, and user-memory indexes.
- Consequence: every operational candidate is reconfirmed with BuenPick. ChromaDB is discarded.

## ADR-009 - Official Meta Channel Only

- Status: accepted
- Decision: Meta WhatsApp Cloud API replaces Baileys and custom bridges completely.
- Consequence: core input is normalized, signature-verified, deduplicated channel data; outbound state distinguishes `accepted`, `sent`, `delivered`, `read`, and `failed`.

## ADR-010 - Delivery Cannot Fail Open

- Status: accepted
- Decision: provider rejection, adapter false, timeout, malformed response, or exception is never converted to success.
- Rationale: the legacy delivery service ignores adapter `success: false` and simulates `delivered` after exceptions.
- Consequence: no simulation exists in production adapters; fake delivery is test-only and explicitly injected.

## ADR-011 - BuenPick Client Semantics

- Status: accepted
- Decision: use bearer auth, bounded timeouts/retries for idempotent reads, typed error mapping, ARS cents, redacted logs, and a hard production-host guard in tests.
- Consequence: empty search is a successful empty collection; pick `404` means unavailable-or-missing; order `401` is non-enumerating auth/ownership failure; `429` and `503` remain distinguishable typed failures.

## ADR-012 - Checkout Remains Disabled

- Status: accepted
- Decision: Piki exposes no internal checkout tool while BuenPick's checkout-session endpoint is disabled.
- Consequence: the purchase action is the confirmed `public_url` returned by pick detail.

## ADR-013 - Observability Is Stage-Based And Redacted

- Status: accepted
- Decision: emit correlated structured events for message, policy, tool, context, template, LLM, grounding, and delivery stages.
- Consequence: stdout/stderr logs must not contain bearer tokens, full phone numbers, message bodies by default, full active-pick payloads, order codes, or raw Meta/BuenPick payloads.

## ADR-014 - n8n Is An Event Consumer

- Status: accepted
- Decision: n8n is limited to handoff, order-status notifications, and daily operations summaries through signed/idempotent APIs or events.
- Consequence: n8n has no direct DB access, reasoning responsibility, or direct Meta access.

## ADR-015 - Legacy Archives Are Untrusted And Sensitive

- Status: accepted
- Decision: no legacy module is copied wholesale; sensitive artifacts are quarantined, revoked where applicable, and removed/redacted before version control.
- Consequence: raw exports remain outside the workspace; active copies contain redaction markers; credential revocation remains an owner checklist item.

## ADR-016 - Container Gate Is Deferred, Not Waived

- Status: accepted
- Decision: Stage 1 has no runtime and therefore no Docker build. Docker availability is still verified now and is mandatory for Stage 2.
- Evidence: `docker version`, `docker compose version`, and `docker info` all reported that Docker is unavailable in this WSL distro and Docker Desktop WSL integration must be enabled.
- Consequence: Stage 2 cannot pass until Docker Desktop integration works.

## ADR-017 - Operator Console Owns Conversations, Not Orders

- Status: accepted
- Decision: recover Delibot's chat/Kanban capability as an authenticated Piki operator console whose board represents conversation and handoff state only.
- Rationale: both legacy extracts contain a functional React/Vite Kanban and ChatView, but their order stages, local catalog, and order creation mix channel operations with commercial truth owned by BuenPick.
- Consequence: manual replies use Piki's idempotent Meta delivery path; the UI renders persisted provider states and never infers success from an optimistic client update.
- Consequence: browser clients cannot call Meta, BuenPick, n8n, or either product database directly. Real-time updates come from a resumable, authenticated Piki event contract.
- Consequence: moving a conversation to human attention pauses automated replies; resuming Piki is an explicit, versioned, audited transition rather than a side effect of dragging a card.

## Unresolved Contract Questions

These do not justify inventing behavior and must be resolved through contract evolution or safe defaults:

1. No pagination/cursor is documented beyond the 20-result search cap.
2. Order ownership mismatch and bad API credentials share `401`.
3. Pick missing and pick currently unavailable share `404`.
4. Commerce opening hours and pickup instructions may be null.
5. No checkout identity/payment contract exists for Piki.
6. The Internal API document retains Delibot naming and a Delibot-named server token variable; Piki client configuration should use Piki-owned names without changing the upstream contract implicitly.
