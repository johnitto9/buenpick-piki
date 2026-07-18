# Legacy Recovery Map

## Scope And Method

This map treats the two concatenated exports as forensic evidence, not as executable source trees. Evidence references use the form `extract:line` and point either to an artifact marker or to the relevant implementation/test line.

Classification vocabulary:

- `MIGRATE_BEHAVIOR`: preserve the externally observable behavior as a new Piki contract or test.
- `REIMPLEMENT`: build a small replacement behind Piki-owned interfaces.
- `REFERENCE_ONLY`: retain as design/history evidence; do not copy into runtime.
- `DISCARD`: do not copy, execute, or depend on it.

## Extraction Integrity

| Source | Declared | Start markers | End markers | Finding |
|---|---:|---:|---:|---|
| Slim extract | 223 | 223 | 223 | Structurally complete concatenation; includes runtime state and Baileys credential artifacts. |
| Large extract | 2,788 | 1,004 | 1,003 | Truncated inside a vendored `pip` file; includes history, failed copies, generated state, and a local virtual environment. |
| Internal API | n/a | n/a | n/a | Complete 402-line operational contract; read in full without network access. |

Evidence: slim header at `codigoslasts/codigo_extraido_delibotlast.txt:1`; large header at `codigoslasts/codigo_extraido_delibotlast1.txt:1`; unmatched final marker at `codigoslasts/codigo_extraido_delibotlast1.txt:247879`.

The large export's claim of 2,788 files is not a usable inventory. Only the 1,004 present start markers may be cited. The primary implementation candidate is the top-level `backend/` tree at lines 59,445-95,608. Trees named `backendv14fail/` and `delibotappv13-fail/`, development histories, root experiments, virtual environments, caches, and generated state are not authoritative runtime.

## Recovery Map

| Legacy artifact / evidence | Finding | Classification | Piki destination |
|---|---|---|---|
| Slim `backend/services/conversation_service.py` (`slim:6933`) | Bounded conversation retrieval and per-customer message persistence are the clearest slim context core. | `MIGRATE_BEHAVIOR` | Conversation repository/service with request-scoped DB sessions; isolation and context-window tests. |
| Slim React/Vite frontend (`slim:20464-22254`) and large equivalent (`large:167976-170002`) | Delibot had an operator surface: a Kanban opened a conversation chat, received real-time events, and allowed a human agent to reply. This operational capability was omitted from the first recovery-map pass. | `MIGRATE_BEHAVIOR` | Piki operator console for conversation triage, durable handoff/takeover, message history, manual replies, and provider delivery truth. |
| Slim `KanbanBoard.jsx` and `ChatView.jsx` (`slim:20605-21351`) | The board used order stages and drag/drop; chat merged history with `new_message` events and distinguished client, bot, and agent senders. Order-centric workflow and optimistic send success are not valid Piki contracts. | `REIMPLEMENT` | Conversation-owned workflow (`new`, `piki_active`, `needs_human`, `human_active`, `resolved`) with audited transitions and Meta-backed reply states. |
| Slim message/order/WebSocket APIs (`slim:4511-4628`, `slim:4691-4823`, `slim:5655`) | REST history, manual agent messages, stage moves, and broadcast events prove the UI was functional, but it was coupled to local orders and an unauthenticated raw WebSocket. | `REIMPLEMENT` | Authenticated operator read/reply/workflow APIs plus resumable server events; no direct Meta, BuenPick DB, or n8n access from the browser. |
| Slim `ProductSearchDialog.jsx` and local quote/order creation (`slim:21668-22082`) | The legacy console searched a local catalog and created commercial records. That duplicates BuenPick operational ownership and conflicts with disabled internal checkout. | `DISCARD` | Read confirmed BuenPick evidence through Piki tools only; use confirmed public purchase URLs and never mutate order truth from the console. |
| Slim `backend/core/tools_registry.py` (`slim:5716`, extraction at `slim:5881`) | Central registry is valuable; regex tags, global singleton, scraper tools, and tool-authored notifications are not. | `REIMPLEMENT` | Typed tool protocols and result envelope; schema validation rather than regex parsing. |
| Slim `backend/services/ai_service.py` (`slim:6343`) | Separates prompt assets, planning, tool extraction, and conversational composition, but is monolithic and uses mutable default arguments. | `REFERENCE_ONLY` | Separate policy, evidence renderer, LLM adapter, and orchestrator ports. |
| Slim `backend/api/webhooks.py` (`slim:5057`) | Shows message -> persistence -> context -> tool -> response sequencing, coupled to legacy payloads and business data. | `MIGRATE_BEHAVIOR` | Channel-neutral inbound application handler after Meta normalization. |
| Slim `backend/tests/test_tool_extraction.py` (`slim:11461`) | Malformed calls, unknown tools, cleaning, validation, and multi-call cases capture useful failure expectations. | `MIGRATE_BEHAVIOR` | Typed tool schema/dispatcher unit tests; no tag-regex compatibility requirement. |
| Slim `backend/tests/test_conversation_persistence.py` (`slim:9485`) | Persistence, bounded context, topic lookup, and DB failure cases are reusable behaviors. | `MIGRATE_BEHAVIOR` | Conversation persistence and failure tests. |
| Large `backend/core/conversation_context.py` (`large:66738`, evidence field at `large:66770`) | Explicit collected context and retrieved evidence support a typed evidence boundary. | `REIMPLEMENT` | `ContextPacket` with confirmed, unavailable, actions, rules, and trace metadata. |
| Large `backend/core/asset_loader_service.py` (`large:66235`) | Central asset loading, validation, caching, and Jinja loading are useful; legacy path traversal, Baileys loading, and global initialization are not. | `REIMPLEMENT` | Package-resource template loader with allowlisted paths and fail-fast validation. |
| Large `backend/core/prompt_manager.py` (`large:68226`) | One prompt/template entry point is useful, but historical versions and hardcoded fallback voice are not. | `REIMPLEMENT` | One system prompt registry plus one evidence-template registry. |
| Large `backend/services/jinja_service.py` (`large:77686`, structured rendering at `large:78072`) | The E2 structured-draft boundary is valuable; embedded catalog formatting and response-writing logic violate Piki's evidence-only rule. | `REIMPLEMENT` | Jinja Evidence Renderer producing task/query/confirmed/unavailable/actions/rules sections. |
| Large template directories (`large:73333-73356`) and snapshot test (`large:93214`) | All template directories are recorded as empty while tests require `.j2` files. The exported Jinja implementation is not executable evidence. | `REFERENCE_ONLY` | New minimal templates and snapshot tests based only on Piki contracts. |
| Large four-stage orchestration (`large:69274-69327`, fusion at `large:69555`) | Context -> Jinja draft -> tool evidence injection -> LLM fusion -> delivery is the main recoverable architecture. Tool execution ordering must move before final evidence rendering. | `MIGRATE_BEHAVIOR` | Policy -> typed tools -> `ContextPacket` -> Jinja -> optional LLM -> grounding -> delivery. |
| Large `backend/services/fusion_selector.py` (`large:77105`) | Multiple response modes are useful; confidence heuristics and version-specific routing are not authoritative. | `REIMPLEMENT` | Explicit deterministic, Jinja, Jinja+LLM, and non-commercial LLM policies. |
| Large `backend/services/state_service.py` (`large:82786`, active topic at `large:82893`) | Per-customer active topic with TTL and Redis/fallback behavior is directly relevant. The fallback logs full topic data. | `REIMPLEMENT` | Redis active pick keyed by channel/account/conversation, TTL, explicit clear, safe fallback, and redacted logs. |
| Large active-topic tests (`large:24973`, `large:25119`) | Search establishes a topic and a later photo request resolves against it. These scripts print data and often do not assert. | `MIGRATE_BEHAVIOR` | Deterministic active-pick integration tests with real assertions and no PII. |
| Large memory service (`large:78783`) and scope tests (`large:93456`) | Scoped TTL, deduplication, importance filter, persistence, and customer isolation are strong contracts. | `MIGRATE_BEHAVIOR` | Redis recent state plus PostgreSQL durable memory with explicit retention and isolation. |
| Large `backend/services/photo_service.py` (`large:80437`) | Contextual photo, URL preflight, factual caption, degraded result, and active-topic follow-up are useful. | `REIMPLEMENT` | `send_pick_image` prepares verified BuenPick media evidence; Meta adapter performs actual media delivery. |
| Large photo tests (`large:89334`, failure assertions at `large:89532`) | Tests require no false photo success on missing/404 media and retain the active topic. Product fixtures themselves are legacy-only. | `MIGRATE_BEHAVIOR` | Media success/degradation contract tests using anonymous pick fixtures. |
| Large grounding enforcement (`large:80911-81071`) | Detecting omission and producing a factual fallback is valuable, but checking only an active product name is insufficient. | `REIMPLEMENT` | Validator checks commercial claims against typed evidence and blocks unsupported claims. |
| Large `backend/services/observability_service.py` (`large:79536`, trace creation at `large:80215`) | Correlated per-message stages and timings are useful. In-memory/global trace state is not production-safe. | `REIMPLEMENT` | Structured events and durable trace/tool/delivery records with redacted identifiers. |
| Large `backend/services/vector_search_service.py` (`large:85780`) | PostgreSQL/pgvector direction and candidate scoring are useful; legacy catalog semantics are not truth. | `REIMPLEMENT` | Separate catalog, stable knowledge, and memory indexes; every operational candidate is reconfirmed through BuenPick. |
| Large memory/pgvector migrations (`large:58714-59444`) | Migration discipline and separate memory schema are useful references, not compatible schemas. | `REFERENCE_ONLY` | New reproducible Alembic migrations owned by Piki. |
| Large golden suites (`large:88024`, `large:88491`) | Tone, placeholder leaks, no invented variants, photo degradation, and single delivery exit are useful expectations; many tests depend on missing assets or live-shaped legacy services. | `MIGRATE_BEHAVIOR` | Piki golden conversation suite with fake LLM, mock BuenPick server, and fake Meta adapter. |
| Large `backend/services/delivery_service.py` (`large:76389`) | Central delivery and sanitization are useful concepts, but implementation reports success on failed adapter results and simulates delivery after exceptions (`large:76570-76633`). | `DISCARD` | New Meta delivery adapter with explicit `accepted/sent/delivered/read/failed` states and no success fallback. |
| Slim/large WhatsApp services (`slim:9184`, `large:86083`) | Custom `BOT_URL`, `/send-image`, local files, and boolean results are legacy bridge contracts. | `DISCARD` | Official Meta Cloud API webhook and outbound adapters. |
| Slim scraper and local catalog (`slim:8642`, calls at `slim:5486`) | Duplicates operational truth and accesses external commerce data. | `DISCARD` | BuenPick Internal API client only. |
| Slim Chroma knowledge service (`slim:7656`, connection at `slim:7707`) | ChromaDB, local vector persistence, and local catalog truth violate fixed decisions. | `DISCARD` | PostgreSQL + pgvector, candidate-only semantics. |
| Large state machine and backup (`large:68718`, `large:70625`) | Duplicated orchestration and versioned backup create a god object and contradictory flows. | `DISCARD` | Small orchestrator composed from interfaces. |
| Historical/failure trees and development history | Useful only to explain past regressions; they duplicate runtime and prompts. | `REFERENCE_ONLY` | No runtime destination. |
| Vendored `venv_local`, caches, reports, local DB/state | Generated or third-party material, not project source. | `DISCARD` | Reproducible locked dependencies, containers, and migrations. |
| Slim `whatsapp-bot/auth/*` (`slim:33741-33887`) | Contains Baileys credential/session artifacts. Values were not copied or inspected further. | `DISCARD` | Revoke/rotate if still usable; remove/redact archive before source control. |
| Large `conversation_states/*` (`large:128800-128895`) | Filenames and content contain conversation identifiers/PII-like data. | `DISCARD` | Anonymous fixtures only; redact/remove archive before source control. |

## Explicit Discard List

- Scraping and every local operational catalog path.
- Baileys, its auth/session state, QR pairing, custom bridge endpoints, and `BOT_URL`.
- ChromaDB and local vector stores.
- Direct BuenPick database access or copied BuenPick business rules.
- Internal Piki checkout while the BuenPick endpoint remains disabled.
- Regex/tool tags as a runtime tool protocol.
- Global DB sessions, state-machine god objects, runtime backup versions, and duplicated prompt trees.
- Hardcoded products, prices, stock, commerce data, mutable hours, and legacy Delify wholesale/retail rules.
- Local filename-based media resolution.
- Delivery simulation, boolean-only delivery, and any fallback that turns rejection into success.
- Legacy order-centric Kanban semantics, local quote/order creation, local product search, and browser-direct operational integrations.
- Secrets, Baileys credential material, real phone identifiers, conversation dumps, local databases, caches, virtual environments, and generated reports.

## BuenPick Internal API Contract

Piki must implement only the documented operational surface:

| Operation | Contract semantics | Piki handling |
|---|---|---|
| `GET /picks/search` | Optional query and commerce filter, max 20; empty `items` is valid. | Empty result is success, not an exception. |
| `GET /picks/{pick_id}` | Returns only currently purchasable picks; unavailable and missing both map to `404`. | Reconfirm before reporting availability, price, stock, media, pickup, or URL. |
| `GET /commerces/{commerce_id}` | Customer-safe commerce data; several fields may be null. | Preserve null/unknown rather than inventing details. |
| `GET /orders/{order_id}` | Requires phone or customer reference ownership proof; mismatch is `401`. | Never query by order ID alone; return a non-enumerating safe error. |
| `POST /checkout-sessions` | Explicitly disabled with `400`. | Do not expose a Piki checkout tool; send confirmed `public_url`. |

Cross-cutting requirements: bearer auth, prices in ARS cents, 120 requests/minute route limit, explicit handling for `400/401/404/429/500/503`, bounded timeout/retry policy, no token logging, and no production calls from tests. Contract evidence: `buenpickinternalapi/INTERNAL_API.md:28-61`, endpoints at lines 87-323, errors at lines 325-339.

## Risks And Contradictions

1. **Sensitive legacy material:** Baileys credential/session artifacts and PII-like conversation state were found. Original exports were quarantined outside the workspace and active copies were redacted. Revocation of any still-valid historical session remains an owner checklist item.
2. **Large extract truncation:** 1,784 declared files are absent and the last present artifact is incomplete. Absence from this export is not proof that a legacy feature did not exist.
3. **Jinja contradiction:** template directories are empty, while runtime and tests assume templates exist. Only the architectural boundary is recoverable.
4. **False delivery success:** failed outbound calls are converted into simulated `delivered` results, and adapter `success: false` is ignored. No legacy delivery code is safe to migrate.
5. **Duplicated runtime:** primary, failed, backup, and historical versions coexist; comments that claim a version is final are not evidence.
6. **Logging exposure:** legacy code logs customer IDs, phone-like conversation IDs, active-topic payloads, tool data, and message previews. Piki needs explicit redaction and data minimization.
7. **API ambiguity:** order ownership failure and authentication failure both use `401`; pick `404` combines absent and currently unavailable. The client must preserve safe user behavior without claiming a more specific fact.
8. **Search limitation:** simple title search, maximum 20 results, and no documented pagination can limit discovery. pgvector may generate candidates but cannot override API confirmation.
9. **Nullable commerce facts:** opening hours and pickup instructions may be null. Responses must state unavailability or omit the claim.
10. **Docker prerequisite:** Docker commands are unavailable in the current WSL distro because Docker Desktop WSL integration is disabled. Stage 2 cannot prove its container gate until this is corrected.
11. **Operator console omission:** the first recovery-map pass missed a complete React/Vite chat and Kanban surface present in both extracts. Recovering it as an order backoffice would recreate forbidden business truth, so Piki must model only its own conversation and handoff workflow.

## Stage 1 Gate Assessment

- No runtime has been implemented: **pass**.
- Recovery map includes artifact, evidence, classification, and destination: **pass**.
- Explicit discard list: **pass**.
- Internal API understood and recorded: **pass**.
- Official Meta Cloud API recorded as the Baileys replacement: **pass**.
- Risks and contradictions documented: **pass**.
- Universal no-secrets condition: **pass for the active workspace after redaction and quarantine**.

Stage 1 is complete. The next task is Stage 2 typed core contracts and minimal health/readiness bootstrap.
