# Piki Status

## Current Stage

- Stage: 8 - pgvector And Synchronization
- Gate: not started
- Runtime implementation: completed and verified Stage 2 through Stage 7

## Completed

- Read every Markdown file in `piki_codex_harness_simple` in the required order.
- Verified that the slim legacy extract, large legacy extract, and BuenPick Internal API contract exist.
- Read the complete BuenPick Internal API contract.
- Indexed 223/223 complete slim artifacts and 1,004 present large-extract artifacts.
- Classified legacy runtime, tests, documentation, failed copies, generated dependencies, state, and sensitive artifacts.
- Created `docs/LEGACY_RECOVERY_MAP.md` with evidence, classification, destination, discards, API contract, risks, and gate assessment.
- Created `docs/GOLDEN_BEHAVIORS.md` with recovered invariants, golden cases, and failure matrix.
- Created `docs/ARCHITECTURE_DECISIONS.md` with Stage 1 decisions and unresolved contract questions.
- Confirmed that no runtime was implemented.
- Quarantined original legacy exports outside the workspace, preserved checksums, and replaced credential/PII-bearing blocks with redaction markers.
- Added repository ignore rules for secrets, legacy session state, local databases, caches, and runtime volumes.
- Added a Python 3.12 package with strict environment settings and structured JSON logging.
- Added versioned, channel-neutral contracts for inbound messages, tools, evidence packets, response modes, and delivery truth.
- Added FastAPI liveness/readiness endpoints with real PostgreSQL and Redis probes and injectable tests.
- Added a graceful worker entrypoint with heartbeat health checking.
- Passed Ruff, strict MyPy, and 13 unit/API tests.
- Added and tested reversible Alembic migration `0001_core_records`.
- Built a 93 MB multistage Piki image running as UID `10001` with no local secrets or legacy exports.
- Started API, worker, PostgreSQL/pgvector, Redis, migration job, and n8n through Docker Compose; all healthchecks passed.
- Verified worker graceful shutdown with exit code `0` and a structured `worker_stopped` event.
- Verified n8n uses an isolated database role that cannot connect to the Piki database.
- Added a parsed Swarm/Dokploy production stack with external secrets, resource limits, rollback policy, and persistent volumes.
- Added owner guidance for Meta WhatsApp Cloud API and n8n, plus Piki voice/evidence direction.
- Passed Ruff, strict MyPy, and 14 unit/API tests after the final Stage 2 changes.
- Added strict response models for search, available pick detail, commerce, and owned orders.
- Added an async BuenPick Internal API client with bearer auth, bounded timeout retries,
  safe error mapping, identifier encoding, and a production-host guard.
- Kept checkout disabled locally and required exactly one ownership proof before order lookup.
- Added typed, channel-neutral tools for search, detail, commerce, owned order, and image evidence.
- Passed all Stage 3 contract, failure, security, type, lint, Docker build, and smoke checks.
- Added Redis-backed active-pick references scoped by channel account and conversation.
- Stored only immutable identifiers and selection metadata; commercial facts are reconfirmed through
  BuenPick on every resolution.
- Proved active-pick isolation and expiry with both controlled unit tests and the real Redis container.
- Added explicit-reference precedence, stale `404` clearing, corrupt-state handling, and honest Redis
  outage results without process-global fallback.
- Added Redis conversation locks with random owner tokens, bounded leases, and atomic compare-delete
  release, plus account-scoped inbound message deduplication with TTL.
- Proved lock ownership and message replay behavior in unit tests and against the real Redis service.
- Added typed pending actions for pick disambiguation and order-ownership prompts, scoped by
  conversation with TTL and atomic single-consumer semantics.
- Added SQLAlchemy async persistence with one session per unit of work, transactional conversation
  upsert, durable inbound-message deduplication, and isolated recent history.
- Proved commit, rollback, deduplication, history ordering, and conversation isolation against the
  real PostgreSQL container.
- Rebuilt the current image and passed the complete Compose health/smoke gate.
- Added the single packaged Piki system prompt and a strict Jinja evidence renderer using
  `StrictUndefined` and JSON-quoted dynamic values.
- Added golden and injection tests for the evidence structure and rejected all Delify/candy/
  wholesale catalog language from runtime prompt assets.
- Proved prompt assets appear exactly once in the wheel and render inside the production image.
- Added a complete typed policy registry for discovery, pick detail, commerce, owned order, image,
  handoff, and non-commercial BuenPick explanations.
- Prohibited evidence-free commercial packets and free-LLM mode for every commercial policy.
- Added a provider-neutral composition contract, Responses API adapter with bounded retries and safe
  parsing, and a deterministic recording fake for tests.
- Added conservative grounding for high-risk facts and internal leaks plus an API-evidence-only
  factual fallback across timeout, refusal, invalid output, and hallucination paths.
- Rebuilt the image, proved packaged grounding, recreated the stack, and passed all healthchecks.
- Added official Meta webhook challenge and raw-body HMAC SHA-256 signature verification.
- Added anonymized payload fixtures and channel-neutral normalization for text, image, interactive,
  unsupported messages, plus sent/delivered/read/failed callbacks.
- Refused to acknowledge valid events when no durable ingress is configured.
- Added official outbound payloads for text, public-link image, reply-button interactive messages,
  and approved templates.
- Distinguished Meta `accepted`, explicit `failed`, and transport-uncertain `unknown`; outbound POST
  is never automatically retried after an uncertain timeout.
- Added durable idempotent delivery attempts plus append-only Meta status events with monotonic
  accepted/sent/delivered/read/failed transitions and audited late regressions.
- Wired webhook ingress to PostgreSQL-first message deduplication, Redis replay hints, and durable
  delivery callback application; missing attempts remain retryable instead of being acknowledged.
- Added Docker-secret-file configuration, startup validation for enabled Meta ingress, production
  Swarm wiring, and an owner checklist for Meta plus deliberately limited n8n operations.
- Made the customer-service window explicit on delivery requests: free-form text, image, and
  interactive sends require confirmed `open`; `closed` or `unknown` fail locally and approved
  templates remain eligible.
- Required a real provider message ID for every accepted/sent/delivered/read delivery result.
- Proved application-owned Meta ingress closes on FastAPI lifespan shutdown, rebuilt the final Stage
  6 image, and passed migration, health, packaged-contract, and full Compose smoke checks.
- Added an executable golden conversation harness over the real policy, ContextPacket, Jinja,
  composition, and grounding pipeline; proved Piki's greeting uses no commercial tools or legacy/
  internal language.
- Added a typed BuenPick search-to-evidence mapper and golden cases for current results, ARS cents,
  and a successful empty search that never becomes an error or fabricated alternative.
- Added a narrow active-pick image preparation use case that reconfirms inherited state, obtains the
  current BuenPick image through the typed tool, and returns safe typed failures without delivery.
- Added goldens proving contextual photo continuity and stale-pick `404` cleanup with no media leak.
- Added typed order evidence and goldens for owned-order status, non-enumerating foreign orders, and
  BuenPick timeout behavior that cannot enter commercial composition.
- Added PII-minimized lifecycle event contracts plus correlated/timed ContextPacket, Jinja, LLM, and
  grounding instrumentation with distinct success, failure, and blocked outcomes.
- Instrumented every typed BuenPick tool with correlated start/finish latency and error codes, plus
  delivery attempts/failures without treating Meta acceptance as delivered success.
- Corrected the recovery map with Delibot's real React/Vite ChatView, Kanban, message API, and
  WebSocket evidence; discarded its local order/catalog behavior and specified a Piki conversation
  console architecture.
- Added durable idempotent handoff requests, one-open-handoff enforcement, and an atomic
  `needs_human` conversation transition as the operator-console data foundation.
- Proved migration `0003_handoff_workflow` upgrade/downgrade/upgrade, real PostgreSQL replay and
  competing-command convergence, rebuilt containers, and passed the complete smoke gate.
- Added `GUIA_PENDIENTES_DUENO.md`, a short owner checklist separating work available now from Meta,
  n8n, deployment, and end-to-end actions that must wait until Stage 9 contracts exist.
- Added `docs/operations/N8N_OWNER_QUICKSTART.md`, a short owner-facing n8n guide clarifying that
  `.env.example` remains the repo template, `.env` is the ignored local runtime file, and n8n should
  stay workflow-free until Stage 9 signed event contracts exist.
- Updated all owner-facing n8n guidance with persistent-state warnings after the local service was
  verified healthy: `.env` changes do not rewrite initialized volumes or PostgreSQL roles, the
  encryption key must remain stable, volume deletion is prohibited as a repair step, and logs come
  before persistent-state changes. Local n8n has an admin account and zero production workflows.
- Prepared the confirmed productive Meta WABA and phone configuration with Graph `v25.0`, generated
  an ignored webhook verify token, mounted local Meta credentials through an explicit Docker secret
  override, and kept ingress disabled.
- Confirmed through sanitized read-only Graph API calls that the productive WABA and Phone Number ID
  match, both WhatsApp management and messaging permissions are granted, and the test Phone Number
  ID is not attached to the productive WABA. No message or Meta mutation was attempted.
- Bound webhook normalization to the configured WABA and Phone Number IDs, expanded altered-body,
  wrong-destination, wrong-mode, 4xx/5xx, incomplete-config, and secret-sanitization coverage, and
  documented the remaining App ID/App Secret blockers plus exact Dokploy/Cloudflare/Meta handoff.
- Added the Meta failure golden with idempotent replay, and moved delivered/failed lifecycle outcomes
  behind the durable PostgreSQL callback commit. Commit failure, sent/read callbacks, duplicates, and
  regressions cannot emit false delivery outcomes.
- Proved the callback path against real local PostgreSQL: delivered applied once, replay converged as
  duplicate, exactly one status event and one success lifecycle record remained, and the controlled
  fixture was removed. Rebuilt API/worker and passed the complete healthy Compose smoke gate with
  Meta ingress still disabled.
- Recovered the productive Meta App ID through an authorized read-only Graph lookup and mapped it
  into the ignored local environment. The owner-supplied App Secret now mounts through an ignored
  Docker secret file and Graph accepted its `appsecret_proof` without exposing the value.
- Rotated the not-yet-registered webhook verify token after a local HTTP test logger rendered its
  query string, then revalidated the replacement only through the in-container secret-file contract.
  No access token was logged, and the retired verify token has never been configured in Meta.
- Reconfirmed n8n healthy with its isolated database and zero workflows. Productive workflows remain
  deferred until Stage 9 publishes signed, idempotent Piki event endpoints.
- Proved the complete local Meta credential set resolves inside the container while ingress remains
  false. A real-secret, synthetic signed webhook persisted once, classified its replay as duplicate
  against PostgreSQL/Redis, and removed its fixture; no Meta message or mutation was attempted.
- Added all remaining Stage 7 goldens for handoff, conversation isolation, prompt injection, and
  surprise-bag contents; all fourteen harness scenarios now have executable coverage.
- Added NVIDIA NIM GLM-5.2 behind the provider-neutral LLM adapter with ignored file-secret loading,
  bounded timeouts, structured failures, and OpenAI-compatible contract tests.
- Added a channel-neutral conversation orchestrator that joins Redis locks, PostgreSQL history,
  intent policy, typed BuenPick tools, Jinja evidence, LLM composition, grounding, and durable replies.
- Added an opt-in same-origin local chat API and responsive Piki console, validated through real HTTP
  requests and desktop/mobile browser checks against the rebuilt container.
- Added durable Meta inbound processing state and worker claims through migration
  `0004_message_processing_outbox`; composition and idempotent delivery are separated from webhook
  acknowledgement, and `accepted` is never promoted to `delivered`.
- Proved the worker path against real PostgreSQL, Redis, Jinja, and GLM-5.2 with a fake delivery
  boundary: one inbound produced one outbound and one accepted attempt, replay sent nothing, no
  delivered state was claimed, and the fixture was removed.
- Passed migration downgrade/upgrade, Ruff, strict MyPy over 60 source files, 163 tests, rebuilt
  Compose healthchecks, full smoke, and a final real local chat/history check.

## Current Task

Define the first Stage 8 semantic-candidate and feature-flag boundary without weakening BuenPick as
the operational source of truth.

## Next Task

Add the smallest reversible pgvector schema and prove that every candidate is reconfirmed through
BuenPick before it can become response evidence.

## Stage 7 Gate Checklist

- [x] All fourteen harness golden scenarios have executable coverage.
- [x] Structured lifecycle events share one trace ID without unnecessary PII.
- [x] Tool, LLM, grounding, and delivery-attempt latencies are measured.
- [x] Dependency and policy failures remain distinguishable in events and results.
- [x] Final quality and Docker gates pass with reproducible evidence.

## Stage 6 Gate Checklist

- [x] Challenge requires the exact configured verify token.
- [x] Invalid `X-Hub-Signature-256` is rejected before parsing or ingress.
- [x] Text, image, interactive, and unsupported payloads normalize to core contracts.
- [x] Sent, delivered, read, and failed callback states remain distinct.
- [x] Redis plus PostgreSQL dedup discards duplicate `wamid` events.
- [x] Outbound text/image/interactive/template delivery preserves provider truth.
- [x] Delivery idempotency and status callbacks persist durably.
- [x] Production ingress and delivery resources close gracefully and pass Docker smoke.

## Stage 5 Gate Checklist

- [x] One short packaged system prompt defines Piki's BuenPick food-rescue identity.
- [x] Jinja renders typed evidence and contains no mutable commercial knowledge.
- [x] Dynamic prompt values are JSON-quoted and injection cannot create evidence sections.
- [x] Prompt assets have a single packaged source and render in the container image.
- [x] Policy registry covers every response mode and commercial route.
- [x] Real LLM adapter contract and deterministic fake are tested.
- [x] Unsupported output and internal-process leaks are blocked by grounding.
- [x] Factual fallback and every response route are proven.
- [x] Rebuilt container image and full Compose smoke gate pass.

## Stage 4 Gate Checklist

- [x] Conversation A active pick cannot contaminate conversation B.
- [x] Active pick resolves and expires through a Redis TTL.
- [x] Explicit pick references take precedence over inherited context.
- [x] Every inherited pick is reconfirmed through the BuenPick client.
- [x] Stale `404` context is cleared and Redis outage fallback is explicit.
- [x] Locks use ownership tokens and safe release.
- [x] Message deduplication is atomic and expires.
- [x] Pending actions are scoped and expire.
- [x] Durable conversation/message persistence is integrated.
- [x] Final unit, failure, Redis, PostgreSQL, Docker health, and smoke gates pass.

## Stage 1 Gate Checklist

- [x] No runtime implemented.
- [x] Recovery map records artifact, evidence, classification, and destination.
- [x] Explicit discard list exists.
- [x] Internal API contract is understood and documented.
- [x] Meta WhatsApp Cloud API is recorded as the Baileys replacement.
- [x] Risks and contradictions are documented.
- [x] Universal gate: active workspace contains no detected credential-shaped values; sensitive legacy blocks are redacted.

## Deferred Security Action

Any historical Baileys session that could still be valid should be revoked from its owning WhatsApp account. Piki will never consume these credentials. This operational follow-up does not block development because the active workspace contains only redacted legacy blocks.

## Stage 2 Gate Checklist

- [x] Typed core contracts are versioned.
- [x] Local application liveness returns `200` in tests.
- [x] Minimum test suite passes.
- [x] No Windows runtime paths or embedded secrets.
- [x] Reproducible migrations exist, upgrade, downgrade, and upgrade again.
- [x] API and worker start in containers as non-root.
- [x] PostgreSQL/pgvector, Redis, and n8n start with healthchecks.
- [x] Full Compose gate and smoke test are demonstrated.

## Stage 3 Gate Checklist

- [x] Empty search is a successful typed result, not an error.
- [x] Pick `404` is mapped without inventing whether it is missing or unavailable.
- [x] Owned-order lookup requires exactly one proof and maps foreign orders to safe `401`.
- [x] Bearer tokens do not appear in logs or safe exceptions.
- [x] Tools return typed evidence/errors and contain no channel delivery behavior.
- [x] Every HTTP test uses `MockTransport`; production host access is rejected by default.
- [x] Search, detail, commerce, and order fixtures align with `INTERNAL_API.md`.
- [x] Checkout remains disabled and performs no request.
- [x] The rebuilt container stack is healthy and its smoke test passes.
