# Piki

### BuenPick's official conversational assistant for food rescue, built on confirmed evidence.

Piki is BuenPick's conversational system for helping people discover surplus-food rescue
opportunities from active businesses, understand their purchase, check an owned order, and request
human attention. Its core safety rule is also its architectural boundary:

> Build a trustworthy representation of reality first. Let the model turn that representation into language second.

Piki does not duplicate BuenPick's commercial rules. It does not scrape, access BuenPick's database,
use unofficial WhatsApp bridges, or let n8n decide commercial facts.

## What Piki provides

- Official Meta WhatsApp Cloud API integration and a local development chat console.
- Durable conversational memory and ephemeral state isolated by channel, account, and conversation.
- Typed search for picks, commerce details, images, and owned orders through BuenPick Internal API.
- Structured evidence assembled with Jinja, explicit policies, and a blocking grounding validator.
- GLM-5.2 through NVIDIA NIM behind a provider-neutral LLM port.
- Idempotent delivery with real provider states: `accepted`, `sent`, `delivered`, `read`, and `failed`.
- Durable human handoff and the foundation for an authenticated operator/Kanban surface.
- Docker Compose development and a Dokploy/Swarm-compatible production path.

## End-to-end architecture

```text
Meta WhatsApp Cloud API
        │ signed, normalized, deduplicated webhook
        ▼
PostgreSQL: durable inbound message + processing outbox
        │ FOR UPDATE SKIP LOCKED claim
        ▼
Redis: locks, replay hints, active pick, TTL state
        ▼
Intent / policy / typed tools
        │
        ├── BuenPick Internal API (operational source of truth)
        │       picks, stock, prices, commerce, orders
        │
        ▼
Evidence mapper → ContextPacket → intelligent Jinja template
        ▼
System prompt + rules + conversation → GLM-5.2/NIM
        ▼
Grounding validator
        │ blocks unsupported claims, internal leaks, and unsafe delivery wording
        ▼
PostgreSQL outbound + IdempotentDeliveryService
        ▼
Meta /messages → accepted
        ▼
Meta callbacks → sent → delivered → read / failed
```

Meta HTTP acceptance is not delivery. Piki emits `delivery_succeeded` only after a durable
`delivered` callback has been committed.

## Components

| Component | Responsibility | Source of truth |
|---|---|---|
| `piki-api` | Readiness, Meta webhook, local chat API, durable ingress | PostgreSQL / Redis |
| `piki-worker` | Outbox claims, composition, official delivery | PostgreSQL + Meta |
| PostgreSQL 16 + pgvector | Conversations, messages, handoffs, delivery, migrations, future semantic indexes | Durable state |
| Redis 7 | Locks, fast deduplication, TTLs, active pick, coordination | Ephemeral state |
| BuenPick Internal API | Picks, prices, availability, commerce, orders | External operational truth |
| Jinja | Converts typed data into evidence | No mutable catalog |
| NVIDIA NIM / GLM-5.2 | Controlled conversational wording | Never a facts database |
| Meta WhatsApp Cloud API | Official channel transport | Final provider delivery state |
| n8n | Future operational event consumer | Never reasoning or chat delivery |

## pgvector and semantic retrieval

The local image uses `pgvector/pgvector:0.8.1-pg16-bookworm` from the beginning, but pgvector is
never a source of truth for stock or availability. Stage 8 defines three separated semantic indexes:

- catalog and candidate retrieval;
- stable BuenPick/Piki knowledge;
- bounded conversational memory.

The invariant is:

```text
pgvector finds candidates
BuenPick reconfirms current reality
Piki answers only from reconfirmed evidence
```

Real embeddings, synchronization, relevance/latency metrics, feature flags, and rollback are the
next implementation stage. An embedding must never turn an expired or sold-out pick into an available
answer.

## BuenPick Internal API

Piki uses Bearer authentication through a typed client with bounded timeouts, safe retries, typed
error mapping, and redacted logs. The supported operational surface is:

- `GET /picks/search` for current results;
- `GET /picks/{pick_id}` to reconfirm a pick;
- `GET /commerces/{commerce_id}` for customer-safe commerce data;
- `GET /orders/{order_id}` only with ownership proof;
- checkout deliberately disabled while the upstream contract keeps it disabled.

An empty search (`items: []`) is a valid result, not an error. Piki never fills in prices, stock,
hours, or surprise-bag contents from model knowledge.

## LLM, Jinja, and grounding

The model never receives arbitrary provider objects or direct tool access. The pipeline builds a
typed `ContextPacket` with:

```text
TASK
QUERY
CONFIRMED DATA
UNAVAILABLE DATA
ACTIONS PERFORMED
WRITING RULES
```

Jinja transforms evidence; it is not a knowledge base or a hardcoded response library. Grounding
blocks unsupported commercial language, internal references, prompt-injection instructions, and
false delivery claims. Provider failures produce a factual fallback or a safe refusal; Piki never
simulates success.

## Docker development

### Safe local profile

Use this profile for development without productive WhatsApp traffic:

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.meta-local.yml \
  -f compose.ai-local.yml \
  up -d --build --wait
```

Local endpoints:

```text
Piki console: http://localhost:8000/console
Readiness:     http://localhost:8000/health/ready
n8n:           http://localhost:5678
```

This profile keeps Meta ingress and the WhatsApp worker disabled. The console supports greetings,
BuenPick explanations, durable history, and human handoff. Productive BuenPick access is protected
by `PIKI_BUENPICK_ALLOW_PRODUCTION=false`.

### Explicit local production profile

`compose.prod-local.yml` enables real BuenPick reads, Meta ingress, and the conversation worker. Use
it only for an authorized test recipient and only when an HTTPS callback publicly routes to this
machine:

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.meta-local.yml \
  -f compose.ai-local.yml \
  -f compose.prod-local.yml \
  up -d --build --wait
```

Meta cannot reach `localhost` directly. Before sending a real WhatsApp message, configure the public
callback, complete the verify challenge, and subscribe the WABA to the `messages` field.

To return to the safe profile, bring the stack up again using only the first three Compose files.
Never use `docker compose down -v`: volumes contain PostgreSQL data and n8n's encrypted state.

## Configuration and secrets

`.env.example` is a template. `.env` is local and ignored. Production uses Docker/Dokploy/Swarm
secrets through `*_FILE` settings whenever possible:

```text
PIKI_META_APP_SECRET_FILE
PIKI_META_ACCESS_TOKEN_FILE
PIKI_META_WEBHOOK_VERIFY_TOKEN_FILE
PIKI_LLM_API_KEY_FILE
PIKI_BUENPICK_INTERNAL_API_TOKEN_FILE
```

Never version `secrets/`, `.env`, access tokens, Meta App Secret, webhook verify tokens, private keys,
database dumps, logs, or n8n credentials. `.dockerignore` is an image-build allowlist, so local
secrets are excluded from the build context. See [SECURITY.md](SECURITY.md).

## n8n boundaries

n8n is an event consumer, not part of conversational reasoning. Its allowed future workflows are:

1. Notify an internal channel when a conversation enters `needs_human`.
2. Send operational order-status notifications.
3. Produce a daily operations summary.

n8n must not call Meta, query PostgreSQL/BuenPick, decide availability, or answer customers. The
current local instance has an administrator and zero productive workflows.

## Observability and delivery truth

Structured lifecycle events are allowlisted and correlated by `trace_id`. They include stage,
outcome, latency, sanitized error codes, and evidence counts, but not full messages, tokens, phone
numbers, raw provider payloads, or unnecessary commercial data.

Delivery is persisted by idempotency key. Meta retries cannot create duplicate conversations or
messages. Provider callbacks advance monotonically; late regressions remain audited without
corrupting the latest known state.

## Tests and gates

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest

DOCKER_BIN="/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" \
  ./scripts/smoke-stage2.sh
```

Coverage includes BuenPick/Meta/LLM contracts, signed webhooks, delivery, failures, deduplication,
golden conversations, prompt injection, handoff, isolation, persistence, migrations, and security
tests. Test suites never call production.

## Roadmap

- **Stages 1–7:** archaeology, contracts, tools, memory, Jinja/LLM, official Meta, goldens, and
  observability: implemented and verified.
- **Stage 8:** real embeddings, pgvector synchronization, and mandatory reconfirmation: next active
  stage.
- **Stage 9:** minimal n8n, authenticated operator Kanban, signed event contracts, and public
  deployment: pending.

Current status is tracked in [PIKI_STATUS.md](PIKI_STATUS.md), reproducible evidence in
[PIKI_EVIDENCE.md](PIKI_EVIDENCE.md), and owner operations in
[GUIA_PENDIENTES_DUENO.md](GUIA_PENDIENTES_DUENO.md).
