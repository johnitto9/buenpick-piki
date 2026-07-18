# Piki Decisions

## Decision Log

### D-001 - Treat extracted legacy code as evidence, not a source tree

- Status: accepted
- Stage: 1
- Context: the repository contains two concatenated text exports rather than executable legacy repositories.
- Decision: reference legacy artifacts by logical path and extract line number; migrate behavior selectively and never copy whole historical modules by default.
- Consequence: Stage 1 documentation must distinguish executable-looking code, tests, historical documentation, dependencies, generated state, and secrets.

### D-002 - BuenPick remains the operational source of truth

- Status: accepted
- Stage: 1
- Decision: stock, price, availability, commerce, pickup, images, order ownership, and public purchase URLs must come from the BuenPick Internal API.
- Consequence: legacy scraper, local catalog, and direct database behavior are not migration candidates.

### D-003 - Meta Cloud API replaces every legacy WhatsApp transport

- Status: accepted
- Stage: 1
- Decision: Baileys, custom bridges, local auth state, and legacy outbound payloads are discard-only evidence.
- Consequence: later channel work will use the official Meta WhatsApp Cloud API behind an adapter.

### D-004 - Reject legacy delivery implementation

- Status: accepted
- Stage: 1
- Context: the large extract's delivery service ignores a false adapter result, labels the attempt delivered/sent, and simulates successful delivery after exceptions.
- Decision: recover the single-exit concept only; discard its implementation.
- Consequence: production adapters can never simulate success, and provider acceptance is distinct from sent/delivered/read callbacks.

### D-005 - Stop progression on sensitive archive exposure

- Status: accepted
- Stage: 1
- Context: the supplied slim export includes Baileys auth/session artifacts and the large export includes PII-like conversation-state artifacts.
- Decision: do not copy or inspect values further; block Stage 2 until quarantine/redaction and credential revocation are demonstrated.
- Consequence: Stage 1 deliverables may be complete while the universal gate remains blocked.

### D-006 - Treat the large extract as truncated evidence

- Status: accepted
- Stage: 1
- Context: it declares 2,788 files but contains 1,004 start markers, 1,003 end markers, and ends within a vendored dependency file.
- Decision: cite only present markers and never infer absence from this export.
- Consequence: tests and templates referenced by code may be missing; new Piki behavior must be proven independently.

### D-007 - Defer Docker execution only until runtime work

- Status: accepted
- Stage: 1
- Context: Docker Desktop WSL integration is not enabled in the current distro.
- Decision: record the failed availability check now; do not waive container requirements for Stage 2.
- Consequence: the Stage 2 Docker gate cannot pass until `docker version`, `docker compose version`, and `docker info` succeed.

### D-008 - Python 3.12 typed service core

- Status: accepted
- Stage: 2
- Decision: use FastAPI, Pydantic v2, SQLAlchemy 2, psycopg 3, Redis asyncio, and structured JSON logs with strict MyPy/Ruff enforcement.
- Consequence: API and worker share domain contracts but have separate entrypoints and lifecycle behavior.

### D-009 - Separate liveness from readiness

- Status: accepted
- Stage: 2
- Decision: liveness reports only process health; readiness probes PostgreSQL and Redis with a bounded timeout.
- Consequence: an infrastructure outage produces readiness `503` without causing a restart loop through the liveness endpoint.

### D-010 - Piki identity belongs in rules, not commercial facts

- Status: accepted
- Stage: 2
- Decision: contracts and later prompt assets describe Piki as BuenPick's practical, warm rescue-market assistant; mutable commercial facts remain typed API evidence.
- Consequence: Delify, candy catalogs, wholesale/retail language, and hardcoded product examples are prohibited in runtime prompt/template assets.

### D-011 - One image for API, worker, and migration jobs

- Status: accepted
- Stage: 2
- Decision: build one multistage, non-root Piki image and select API, worker, or Alembic through the container command.
- Consequence: release artifacts cannot drift between application processes; dev dependencies and legacy extracts stay outside the image.

### D-012 - Isolate n8n at database and network boundaries

- Status: accepted
- Stage: 2
- Decision: n8n receives its own PostgreSQL database and role; public access is limited to its editor endpoint and it shares no Piki database credentials.
- Consequence: n8n cannot query Piki tables and remains an event/API consumer in Stage 9.

### D-013 - Migrations are pre-deploy jobs

- Status: accepted
- Stage: 2
- Decision: local Compose runs a one-shot migration service; Swarm/Dokploy runs the same immutable image as a pre-deploy replicated job.
- Consequence: API replicas never race to migrate on startup, and application rollback remains distinct from schema rollback.

### D-014 - BuenPick responses become strict evidence before tools expose them

- Status: accepted
- Stage: 3
- Decision: validate every supported Internal API response into frozen Pydantic models, keep ARS values as integer cents, and expose them through channel-neutral `ToolResult` values.
- Consequence: empty results remain successful evidence, malformed upstream data fails closed, tools cannot compose or deliver messages, and commercial facts never come from templates or local state.

### D-015 - Order ownership is mandatory and non-enumerating

- Status: accepted
- Stage: 3
- Decision: require exactly one of `customer_phone` or `customer_reference` before any order request and preserve the API's shared `401` meaning for authentication and ownership failures.
- Consequence: knowing an order ID is insufficient, failures do not reveal whether an order exists, and no client-side ownership shortcut is introduced.

### D-016 - Production BuenPick access requires explicit opt-in

- Status: accepted
- Stage: 3
- Decision: reject the production host unless `PIKI_BUENPICK_ALLOW_PRODUCTION=true`; contract tests always use an injected HTTPX mock transport on a reserved `.invalid` host.
- Consequence: development and CI cannot accidentally call the operational API while production deployment remains a documented configuration action.

### D-017 - Active pick stores identity, never commercial snapshots

- Status: accepted
- Stage: 4
- Decision: persist only `pick_id`, `commerce_id`, selection time, and selection source in Redis under a hashed channel-account/conversation key with an atomic TTL.
- Consequence: follow-up requests reconfirm the pick through BuenPick before using price, stock, pickup, image, or URL data; expired or `404` picks cannot leak stale facts.

### D-018 - Redis failure is a typed state outcome

- Status: accepted
- Stage: 4
- Decision: return `state_unavailable` for inherited context when Redis fails, while allowing an explicit pick reference to be confirmed directly and reporting whether its context was persisted.
- Consequence: Piki can ask for clarification or continue from explicit evidence without process-global state, cross-conversation leakage, or simulated persistence.

### D-019 - Coordination uses atomic Redis ownership primitives

- Status: accepted
- Stage: 4
- Decision: acquire conversation locks with `SET NX EX`, release only through a Lua compare-and-delete using a random owner token, and claim inbound message IDs with account-scoped `SET NX EX` dedup keys.
- Consequence: one worker owns a conversation lease at a time, an expired worker cannot release a successor's lock, and webhook replays cannot repeat side effects while the dedup window is active.

### D-020 - Pending actions are narrow, expiring, and single-consumer

- Status: accepted
- Stage: 4
- Decision: model only pick disambiguation and order-ownership prompts, store identifiers rather than commercial snapshots or ownership proofs, and consume actions atomically through Redis `GETDEL`.
- Consequence: two workers cannot continue the same prompt, stale prompts expire, candidate picks must be reconfirmed before use, and sensitive customer proof is never cached in pending state.

### D-021 - Durable writes use an explicit unit of work

- Status: accepted
- Stage: 4
- Decision: own one async SQLAlchemy engine per application resource, create an `AsyncSession` per unit of work, commit on successful context exit, rollback on every exception, and inject sessions into repositories.
- Consequence: there are no global database sessions, conversation and message writes are atomic, Redis dedup remains an optimization, and PostgreSQL uniqueness protects replay across cache loss or restarts.

### D-022 - Prompt assets separate Piki identity from evidence

- Status: accepted
- Stage: 5
- Decision: keep one short packaged system prompt for Piki's Rioplatense BuenPick identity and one Jinja template that only labels and serializes `ContextPacket` evidence; JSON-quote every dynamic string and fail on undefined values.
- Consequence: templates cannot become a candy/catalog knowledge base, user text cannot fabricate evidence headings, mutable commercial facts remain API-derived, and the same assets ship in local, wheel, and container execution.

### D-023 - Response policy is a typed registry

- Status: accepted
- Stage: 5
- Decision: define each route's task, response mode, allowed tools, evidence requirement, and context-specific writing rules in one immutable registry.
- Consequence: commercial routes cannot use free-LLM mode or build an evidence-free `ContextPacket`; image and handoff remain deterministic; templates only display the selected policy rather than deciding behavior.

### D-024 - LLM integration uses a provider-neutral core boundary

- Status: accepted
- Stage: 5
- Decision: make the core depend on `LLMAdapter`, implement the OpenAI Responses API through HTTPX, keep provider/model/key explicit, send no tools, request no storage, parse every `output_text` item, and treat refusals/incomplete/empty responses as failures.
- Consequence: a model cannot call BuenPick or delivery directly, provider secrets stay inside the adapter, tests exercise the real wire contract through `MockTransport`, and another provider can implement the same core protocol.

### D-025 - Grounding is blocking and falls back to API evidence

- Status: accepted
- Stage: 5
- Decision: reject internal pipeline markers, internal references, unsupported currencies, quantities, times, and URLs, plus claims about explicitly unavailable surprise-bag contents; never repair suspect text in place.
- Consequence: blocked, refused, invalid, or timed-out composition returns a deterministic summary built only from confirmed BuenPick API values, with unsafe control text omitted and no false commercial claim reaching delivery.

### D-026 - Meta webhook acknowledgement follows durable ingress

- Status: accepted
- Stage: 6
- Decision: verify the GET challenge separately, validate POST HMAC over exact raw bytes before JSON parsing, normalize Meta payloads behind a channel adapter, and return `503` when no real ingress is available.
- Consequence: invalid signatures never reach the core, Meta-specific shapes stop at the boundary, and Piki never acknowledges then silently drops a valid event.

### D-027 - Uncertain Meta POST outcomes are not retried blindly

- Status: accepted
- Stage: 6
- Decision: return `accepted` only with a valid provider message ID, return `failed` for explicit Meta rejection or local contract rejection, and return `unknown` for timeout, network ambiguity, or malformed success; do not retry the POST inside the adapter.
- Consequence: Piki never labels API acceptance as delivery and avoids creating duplicate WhatsApp messages when a request may have reached Meta before connectivity failed.

### D-028 - Delivery truth is durable and monotonic

- Status: accepted
- Stage: 6
- Decision: claim each outbound request once by idempotency key, persist the adapter result before returning it, append every distinct provider status callback, and update the current attempt only along accepted-to-read progress or an allowed failure transition.
- Consequence: replay cannot resend an already claimed message, acceptance remains distinct from delivery, duplicate callbacks are harmless, and late regressions remain audited without corrupting the latest known state.

### D-029 - PostgreSQL is the inbound replay authority

- Status: accepted
- Stage: 6
- Decision: persist normalized inbound messages transactionally before marking their `wamid` in Redis; use the cache as a replay hint while retaining the PostgreSQL uniqueness constraint as the durable authority.
- Consequence: Redis loss cannot erase acknowledged messages, cache failure after commit does not make ingress unsafe, and a callback without its durable outbound attempt returns a retryable failure.

### D-030 - Enabled Meta ingress fails configuration early

- Status: accepted
- Stage: 6
- Decision: accept direct secrets for ignored local `.env` use and Docker secret-file paths for production, but reject `PIKI_META_INGRESS_ENABLED=true` unless both signing and verification secrets resolve at startup.
- Consequence: a production API cannot appear healthy while every Meta callback fails for missing verification material, and the same application image remains usable in Compose and Swarm/Dokploy.

### D-031 - Free-form Meta delivery requires an explicit open window

- Status: accepted
- Stage: 6
- Decision: carry `open`, `closed`, or `unknown` customer-service-window evidence on each delivery request; allow non-template payloads only for confirmed `open`, while approved templates remain eligible for a closed or unknown window.
- Consequence: missing session knowledge fails before any provider POST, closed-window traffic cannot accidentally masquerade as ordinary conversation, and Meta rejection still remains the final authority for a submitted template.

### D-032 - Golden conversations exercise the real response pipeline

- Status: accepted
- Stage: 7
- Decision: keep a reusable test harness that selects a real typed policy, builds its real ContextPacket, renders packaged Jinja, invokes a scripted provider-neutral LLM adapter, and applies production grounding; only external dependency results are scripted.
- Consequence: golden cases specify user-visible behavior without snapshots of private provider APIs, test doubles cannot bypass policy or grounding, and failures localize to the same boundaries used by runtime composition.

### D-033 - Tool results need explicit evidence mappers

- Status: accepted
- Stage: 7
- Decision: convert typed operational tool results into immutable evidence bundles before policy packet construction; for search, format API cents as ARS, preserve each pick's internal reference outside user text, and represent an empty successful response as confirmed absence.
- Consequence: Jinja never introspects arbitrary API objects, commercial wording remains grounded in a bounded schema, and empty results cannot be confused with upstream failure.

### D-034 - Image preparation stops before channel delivery

- Status: accepted
- Stage: 7
- Decision: coordinate inherited active-pick resolution and the typed image tool in a small use case that returns confirmed evidence plus a public media URL or a typed safe failure; keep response wording and Meta delivery outside it.
- Consequence: contextual photo requests reconfirm availability before media selection, stale state is cleared on BuenPick `404`, tests can prove the exact boundary, and neither the tool nor use case can report provider delivery.

### D-035 - Order evidence excludes ownership proof and customer delivery data

- Status: accepted
- Stage: 7
- Decision: after BuenPick has validated ownership, map only returned status, commerce, pick summary, total, fulfillment type, pickup code/instructions, and commerce pickup address into conversational evidence; keep order ID as an internal reference and omit ownership proof plus customer delivery fields.
- Consequence: the LLM receives enough confirmed data to answer an owned-order query but cannot echo phone/reference proof or delivery-address PII, while shared `401` failures stay non-enumerating and evidence-free.

### D-036 - Lifecycle records are allowlisted, correlated, and text-free

- Status: accepted
- Stage: 7
- Decision: emit a fixed event enum with trace ID, component, outcome, nonnegative duration, optional error code, and aggregate evidence counts; do not accept arbitrary metadata, user text, evidence values, phone, conversation, order, or pick identifiers.
- Consequence: operational traces can measure and distinguish pipeline stages without becoming a second PII store, while a null sink keeps core tests and alternate deployments provider-neutral.

### D-037 - Provider acceptance is an attempted delivery event

- Status: accepted
- Stage: 7
- Decision: emit `delivery_attempted/succeeded` for a persisted Meta acceptance and `delivery_attempted/failed` plus `delivery_failed/failed` for explicit rejection or uncertain transport; never emit `delivery_succeeded` until a later provider `delivered` callback is durably applied.
- Consequence: dashboards cannot inflate accepted API requests into delivered WhatsApp messages, while attempts, failures, timings, and provider error codes remain operationally visible.

### D-038 - Recover the operator console as a conversation surface

- Status: accepted
- Stage: 7/9
- Decision: recover Delibot's functional React/Vite chat and Kanban behavior as an authenticated Piki console whose columns represent Piki-owned conversation/handoff workflow, never BuenPick order state.
- Consequence: manual replies use the shared idempotent Meta delivery service and persisted provider states; local product search, quote/order creation, browser-direct integrations, and optimistic delivery success are discarded.

### D-039 - Open handoff requests converge durably

- Status: accepted
- Stage: 7
- Decision: scope handoff idempotency keys to a conversation, permit at most one `requested` or `claimed` handoff per conversation, and atomically move that conversation to `needs_human` when a request is persisted or replayed.
- Consequence: Meta retries and competing handoff commands cannot create duplicate operator work, while the persisted handoff and workflow state can drive the future board and n8n notification event.

### D-040 - Productive Meta ingress is asset-bound and opt-in

- Status: accepted
- Stage: 7/9
- Decision: bind normalized webhook events to the configured WABA ID and Phone Number ID, reject signed events for any other Meta asset, mount local credentials only through an explicit Compose override, and default production ingress to disabled until the public callback gate is complete.
- Consequence: test-number events cannot enter the productive conversation namespace, a parsed production stack cannot activate ingress accidentally, and delivery configuration can be validated without sending a message or exposing credentials.

### D-041 - Delivery outcome telemetry follows the callback commit

- Status: accepted
- Stage: 7
- Decision: emit `delivery_succeeded` only after a `delivered` callback exits the PostgreSQL transaction successfully, and emit `delivery_failed` only after a `failed` callback commits; do not emit either outcome for accepted, sent, read, duplicate, missing, regressive, or rolled-back callbacks.
- Consequence: dashboards reflect durable provider truth, commit failure cannot manufacture delivery success, and Meta callback replay remains observable in persistence without duplicating operational outcomes.

### D-042 - NVIDIA NIM is isolated behind the provider-neutral LLM port

- Status: accepted
- Stage: 7
- Decision: use NVIDIA NIM's OpenAI-compatible chat-completions endpoint through a dedicated adapter, with the model, base URL, timeout, and API key-file path supplied by configuration.
- Consequence: GLM-5.2 can power Piki without leaking provider details into policy, evidence, tools, or grounding, and another provider can replace it through the existing `LLMAdapter` contract.

### D-043 - The local chat console is an explicit development surface

- Status: accepted
- Stage: 7
- Decision: expose the same-origin local chat API and responsive console only when `PIKI_LOCAL_CONSOLE_ENABLED=true`; keep it separate from the future authenticated operator Kanban.
- Consequence: the end-to-end conversational core can be exercised locally without exposing an unauthenticated production chat or weakening the operator-console authorization boundary.

### D-044 - Meta inbound processing uses a durable PostgreSQL outbox

- Status: accepted
- Stage: 7/9
- Decision: persist accepted Meta inbound messages as pending work, claim them with PostgreSQL `FOR UPDATE SKIP LOCKED`, compose through the channel-neutral orchestrator, and deliver through the existing idempotent Meta service from the worker.
- Consequence: webhook acknowledgement remains fast and durable, process crashes can recover stale claims, duplicate events cannot send twice, and provider `accepted` remains distinct from `delivered`.
