# Piki Operator Console Architecture

## Purpose

The operator console recovers Delibot's useful chat and Kanban behavior without recovering its local
order backoffice. It is a Piki-owned surface for conversation triage, human takeover, message history,
manual replies, and delivery visibility.

## Ownership Boundary

| Concern | Owner |
|---|---|
| Pick, price, stock, commerce, availability, order, checkout | BuenPick Internal API |
| WhatsApp acceptance and delivery state | Meta WhatsApp Cloud API, persisted by Piki |
| Conversation, handoff, assignment, automation mode, audit trail | Piki PostgreSQL |
| Short locks, replay hints, presence, transient coordination | Piki Redis |
| Operator rendering and commands | `piki-console` |
| Operational automations and summaries | n8n through signed Piki events/APIs only |

The browser never calls Meta, BuenPick, n8n, or a database directly.

## Conversation Workflow

The Kanban columns describe Piki's attention workflow, not commercial order status:

1. `new`: durable inbound exists and has not yet been classified.
2. `piki_active`: automation may answer using the evidence-first pipeline.
3. `needs_human`: a handoff is open and automated replies are paused.
4. `human_active`: an operator claimed the conversation; automation remains paused.
5. `resolved`: no open handoff; reopening is explicit when a new inbound arrives.

Every transition carries the expected workflow version. Conflicts return the current record instead of
silently overwriting another operator. Actor, reason, trace, prior state, next state, and time are
append-only audit evidence.

## Initial Service Contracts

- `GET /operator/conversations`: filtered, cursor-based board projection.
- `GET /operator/conversations/{id}/messages`: bounded cursor history with sender and delivery state.
- `POST /operator/conversations/{id}/handoffs`: idempotently request human attention.
- `POST /operator/conversations/{id}/claim`: claim an open handoff with expected version.
- `POST /operator/conversations/{id}/workflow`: explicit versioned transition.
- `POST /operator/conversations/{id}/replies`: persist intent, use the shared idempotent delivery
  service, and return Meta truth (`accepted`, `failed`, or `unknown`).
- `GET /operator/events`: authenticated resumable SSE stream using durable event IDs. WebSocket may be
  introduced only if bidirectional transport is later proven necessary.

Authentication and authorization are required before these routes become public. Identity integration
is intentionally separate from BuenPick customer ownership proof.

## Frontend Shape

`piki-console` will be a Dockerized React/TypeScript application with a compact board/list switcher,
conversation panel, message timeline, assignment controls, and delivery-state indicators. A manual
reply appears as pending until the API returns a persisted attempt; it becomes delivered only after a
durable Meta callback. Failed and unknown states remain visible and retry is an explicit new attempt.

The console may display confirmed BuenPick evidence already attached to the conversation. It cannot
create a local pick, quote, order, checkout, price, stock value, or order-state mutation.

## Delivery And Automation Invariants

- `needs_human` and `human_active` suppress automated outbound messages.
- Manual replies use the same customer-service-window enforcement and official Meta adapter as Piki.
- A browser disconnect cannot lose a committed handoff or turn a failed send into success.
- Event replay and initial REST projections converge on the same PostgreSQL state.
- Conversation content is never placed in event URLs, logs, metrics labels, or n8n payloads by default.

## Delivery Sequence

1. Stage 7 persists idempotent handoffs and proves handoff/isolation/failure goldens.
2. Stage 8 verifies operator API threat boundaries, concurrency, event replay, and manual delivery.
3. Stage 9 adds the `piki-console` container, production auth integration, resource limits, smoke tests,
   backup/restore coverage, and Dokploy/Swarm deployment wiring.
