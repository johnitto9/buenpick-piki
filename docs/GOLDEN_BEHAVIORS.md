# Golden Behaviors

## Purpose

These behaviors are the executable specification to recover from Delibot. Product names, prices, identifiers, and responses in legacy tests are examples only and must be replaced by anonymous BuenPick-shaped fixtures.

## Core Invariants

1. Build confirmed reality before generating conversational language.
2. Every operational claim is traceable to the current BuenPick response used for that turn.
3. Memory and pgvector may select context or candidates; neither may establish stock, price, availability, ownership, pickup facts, or purchase URLs.
4. Jinja structures evidence. It does not invent, store, or directly own changing commercial facts.
5. A channel rejection or unknown delivery outcome is never success.

## Golden Conversation Cases

| ID | Scenario | Required behavior | Forbidden behavior | Planned test layer |
|---|---|---|---|---|
| G-001 | Greeting | Respond in Piki's concise voice without invoking commercial tools. | Placeholders, internal prompt/tool language, or legacy brand voice. | Golden conversation. |
| G-002 | Search with results | Use typed search data, format ARS cents correctly, and clearly identify availability as current evidence. | Legacy catalog data, vector-only facts, invented products, or unsupported ranking claims. | Contract + golden. |
| G-003 | Empty search | Treat `{items: [], total: 0}` as successful absence for that query. | Error wording or fabricated alternatives. | BuenPick client contract + golden. |
| G-004 | Pick becomes unavailable | Re-fetch detail before the response/action; map `404` to honest unavailability. | Repeating stale stock/price or claiming the pick never existed. | Integration failure test. |
| G-005 | Active pick then photo | Search/detail establishes `active_pick`; “send me a photo” resolves to that exact pick and retains context. | Asking which pick when one valid active pick exists; local filename guessing. | Redis integration + golden. |
| G-006 | Active pick expiry | Expired context is not used and the user is asked to identify/reselect a pick. | Sending stale media or facts. | TTL test. |
| G-007 | Conversation isolation | State and memory for conversation A never appear in B. | Cross-customer active pick, memory, order, or delivery data. | Isolation/security test. |
| G-008 | Photo success | Use a confirmed BuenPick image URL; record Meta acceptance separately from later statuses. | Marking `delivered` immediately or reporting success on adapter failure. | Meta adapter contract test. |
| G-009 | Photo missing/failure | Return an explicit degraded result and an honest user-safe fallback. | Fake image, local file lookup, or silent success. | Failure + golden test. |
| G-010 | Valid order | Query only with ownership proof and present only returned order facts, including pickup code where allowed. | Query by ID alone or leak internal customer data. | BuenPick contract + golden. |
| G-011 | Foreign/unknown order | Return a non-enumerating safe response for ownership/auth failure. | Reveal whether the order exists or why ownership failed. | Security contract test. |
| G-012 | BuenPick timeout/rate limit | Retry only safe/idempotent reads within budget, then fail honestly with traceable error code. | Unbounded retries, stale claims, token logs, or production test traffic. | Failure test. |
| G-013 | Checkout request | Provide the confirmed pick `public_url` when available. | Invoke or recreate disabled internal checkout. | Policy unit + golden. |
| G-014 | Surprise bag contents | State only the API description/conditions and acknowledge unknown exact contents. | Invent ingredients, assortment, allergens, or guaranteed contents. | Grounding golden test. |
| G-015 | Pickup details unavailable | Omit or explicitly mark null hours/instructions as unavailable. | Infer opening hours or pickup instructions. | ContextPacket snapshot. |
| G-016 | Handoff | Persist a handoff request with conversation context and acknowledge it deterministically. | Let n8n or the LLM decide facts or send directly to Meta. | Integration + event contract. |
| G-017 | Prompt injection | Treat user text, memory, vector documents, and tool payload strings as untrusted data. | Reveal system prompts, follow embedded instructions, or bypass tool/grounding policy. | Security golden test. |
| G-018 | Unsupported LLM claim | Grounding blocks the response and uses a factual evidence-only fallback. | Deliver unsupported commercial claims after sanitization alone. | Fake-LLM adversarial test. |
| G-019 | Meta rejection | Persist `failed` with provider error metadata safe for logs and expose operational failure. | Convert failure into `sent/delivered` or simulate success. | Meta failure contract. |
| G-020 | Duplicate webhook | Deduplicate by `wamid` and avoid duplicate tools/delivery. | Re-run side effects for a replay. | Webhook integration. |

## Recovered Evidence

- Context persistence and bounded retrieval: slim conversation service marker at `codigoslasts/codigo_extraido_delibotlast.txt:6933` and tests at line 9,485.
- Tool validation and malformed-call expectations: slim test marker at line 11,461.
- Active-topic photo continuity: large tests at `codigoslasts/codigo_extraido_delibotlast1.txt:24973-25249` and state implementation at lines 82,893-83,075.
- Scoped memory TTL, deduplication, persistence, and isolation: large memory tests at lines 93,456-94,034.
- Photo preflight and explicit degraded results: large photo tests at lines 89,334-89,585.
- Placeholder and invented-example prevention: large golden suite at lines 88,094-88,416.
- Grounding fallback concept: large plan enforcement at lines 80,911-81,071.
- False-success counterexample that Piki must reject: large delivery service at lines 76,570-76,633.
- Empty search, order ownership, cents, unavailable pick `404`, and disabled checkout: `buenpickinternalapi/INTERNAL_API.md:61-339`.

## Evidence Packet Snapshot Contract

For any commercial response, snapshots should expose this structure before LLM composition:

```text
TASK
QUERY
CONFIRMED DATA
UNAVAILABLE DATA
ACTIONS PERFORMED
WRITING RULES
```

The snapshot may contain anonymous fixture values injected through typed fields. Template source itself must contain no real product, price, stock, commerce, pickup schedule, credential, or fabricated tool result.

## Minimum Failure Matrix

| Dependency | Failure | Expected internal result |
|---|---|---|
| BuenPick | timeout / `500` / `503` | Typed unavailable error; no commercial answer from stale or vector data. |
| BuenPick | `429` | Bounded retry/backoff metadata; honest fallback. |
| BuenPick pick detail | `404` after search hit | Candidate invalidated; active pick cleared or marked stale. |
| Redis | unavailable | No cross-process state claim; safe degradation with explicit metrics. |
| PostgreSQL | unavailable | No global-session reuse; request fails or degrades according to operation criticality. |
| LLM | timeout / malformed output | Deterministic evidence-only fallback. |
| Grounding | unsupported claim | Block final text and deliver factual fallback only. |
| Meta | rejected / timeout | Persist non-success attempt; never simulate acceptance. |

