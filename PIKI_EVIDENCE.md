# Piki Evidence

## Evidence Policy

- Commands are run from the repository root unless stated otherwise.
- No command may call the production BuenPick API during tests.
- Secret values are never recorded; only affected logical artifact paths and remediation are documented.

## 2026-07-16 - Stage 1 / Tracking Initialization

### Source verification

Command:

```bash
wc -l -c codigoslasts/codigo_extraido_delibotlast.txt \
  codigoslasts/codigo_extraido_delibotlast1.txt \
  buenpickinternalapi/INTERNAL_API.md
```

Result:

- Slim extract: 33,894 lines, 1,372,716 bytes.
- Large extract: 248,128 lines, 10,387,456 bytes.
- Internal API contract: 402 lines, 9,137 bytes.
- The Internal API contract was read completely; no network request was made.

### Repository baseline

Command:

```bash
git status --short
```

Result: the directory is not currently a Git repository. This is an environment constraint, not evidence of a clean or dirty worktree.

### Marker integrity baseline

Commands:

```bash
rg -c '^--- Inicio del archivo: ' <extract>
rg -c '^--- Fin del archivo: ' <extract>
```

Result:

- Slim: 223 starts and 223 ends, matching its declared 223 files.
- Large: 1,004 starts and 1,003 ends, despite declaring 2,788 files.
- The large extract ends inside `venv_local/lib/python3.10/site-packages/pip/_internal/req/req_file.py`; it is truncated and contains vendored environment noise.

## 2026-07-16 - Stage 1 / Recovery Map

### Artifact indexing

Commands:

```bash
rg -n '^--- Inicio del archivo: ' <extract>
rg -n '^--- Carpeta: ' <extract>
rg -n -i '<behavior keywords>' <extract>
sed -n '<artifact start>,<artifact end>p' <extract>
```

Result:

- The slim primary runtime candidates are under `backend/` and include conversation, tools, AI composition, webhook, scraper, Chroma, WhatsApp bridge, and tests.
- The large primary runtime candidate is the top-level `backend/` tree. `backendv14fail/`, `delibotappv13-fail/`, histories, caches, generated reports, and `venv_local/` are non-authoritative.
- Large Jinja template directories are empty, although `backend/tests/unit/test_jinja_snapshots.py` requires templates. The legacy Jinja runtime cannot be treated as executable proof.
- Active-topic, memory-scope, photo-degradation, placeholder, grounding, and observability evidence was mapped to Piki behaviors.

### False delivery success

Command:

```bash
nl -ba codigoslasts/codigo_extraido_delibotlast1.txt | sed -n '76540,76640p'
```

Result:

- Line 76,610 receives the adapter result.
- Line 76,611 creates a `delivered` result without checking the adapter's `success` field.
- Lines 76,613-76,615 fall back to simulated delivery after exceptions.
- Lines 76,618-76,620 return `sent` regardless of that adapter result.
- This implementation is classified `DISCARD`; Piki must preserve real provider states.

### Sensitive artifact detection

Commands inspected logical artifact markers only; secret values were not printed or copied:

```bash
rg -n '^--- Inicio del archivo: ' <extract> | rg -i '(auth|creds|pre-key|session|conversation_states)'
```

Result:

- The slim extract contains a Baileys auth tree including credential, pre-key, and session artifacts.
- The large extract contains persisted conversation-state artifacts with phone-like identifiers.
- Stage progression stopped per the project secret-exposure rule. Remediation is required before Stage 2.

### BuenPick contract validation

Command:

```bash
rg -n '^(##|###)|GET /internal|POST /internal|centavos|401|404|429|503|120 requests|No está habilitado|public_url' buenpickinternalapi/INTERNAL_API.md
```

Result:

- Search, detail, commerce, owned order, and disabled checkout operations are documented.
- Empty search is valid; prices are ARS cents; pick `404` conflates missing/unavailable; order `401` conflates auth/ownership; checkout is disabled; route limit is 120 requests/minute.
- No request was made to `api.buenpick.com.ar`.

### Docker availability

Commands:

```bash
docker version
docker compose version
docker info
```

Result: all three commands reported that `docker` is unavailable in this WSL 2 distro and Docker Desktop WSL integration must be enabled. No Docker claim is made for Stage 1; this is a Stage 2 prerequisite.

### Deliverable validation

Commands:

```bash
find docs -maxdepth 1 -type f -printf '%f\n' | sort
rg -o '`(MIGRATE_BEHAVIOR|REIMPLEMENT|REFERENCE_ONLY|DISCARD)`' docs/LEGACY_RECOVERY_MAP.md
find . -maxdepth 2 -type f <filters excluding supplied inputs and Markdown>
rg -n -i '<secret-value patterns>' PIKI_*.md docs/*.md
```

Result:

- All three Stage 1 deliverables exist.
- Recovery map coverage: 10 `MIGRATE_BEHAVIOR`, 12 `REIMPLEMENT`, 5 `REFERENCE_ONLY`, and 9 `DISCARD` entries.
- No non-document runtime file was created.
- Authored-document secret-value scan passed.

## 2026-07-16 - Stage 1 / Sensitive Archive Remediation

Actions and results:

- Copied both original legacy exports to `/home/juan/.local/share/piki-quarantine/20260716` on the native WSL filesystem.
- Verified both originals against a relative `SHA256SUMS` manifest.
- Verified quarantine modes: directory `0700`, files `0600`.
- Replaced Baileys auth/session blocks, persisted conversation-state blocks, credential-shaped values, and identified sensitive historical artifacts with explicit redaction markers in the workspace copies.
- Preserved extraction marker integrity: slim 223 starts/223 ends; large 1,004 starts/1,003 ends (the original large export remains truncated).
- High-confidence secret-shape scan over active inputs and authored documents passed.
- Added `.gitignore` coverage for environment files, keys, auth/session state, local databases, caches, virtual environments, and runtime volumes.
- Remote revocation of historical Baileys sessions is intentionally tracked as an owner action; Piki does not depend on them.

## 2026-07-16 - Stage 2 / Typed Bootstrap

Environment setup:

- System Python: 3.12.3.
- Native `venv` support was unavailable, so the already-installed `virtualenv` package created `.venv`; no PostgreSQL, Redis, pgvector, or n8n package was installed on WSL.
- Project and development dependencies were installed from the package registry using exact versions in `pyproject.toml`.

Commands:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest -q
```

Result:

- Ruff: all checks passed.
- MyPy strict: no issues in 12 source files.
- Pytest: 13 passed.
- Tests prove liveness `200`, readiness `200/503`, production docs disabled, resource shutdown, settings validation, typed tool failures, evidence separation, delivery truth, image URL requirements, and worker heartbeat freshness.
- No test called the BuenPick production API.

## 2026-07-16 - Stage 2 / Docker And Migration Gate

Docker availability:

- WSL integration is not on PATH, but Windows Docker Desktop was found at `C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe` and invoked directly.
- Docker client/engine: 29.5.2; Docker Desktop: 4.76.0; Compose: v5.1.4.

Verified results:

- `docker compose config --quiet`: passed.
- Multistage build: passed; runtime image size 93,274,931 bytes; configured user `piki`; runtime UID `10001`.
- Image filesystem check: only application package dependencies, Alembic config, and migrations; no `.env`, Windows paths, auth state, or legacy exports.
- Image history scan found no local placeholder secrets or future API secret names.
- Migration ran to `0001_core_records`; downgrade to base and re-upgrade both passed.
- A fresh empty-volume PostgreSQL initialization created the separate n8n role/database and denied that role access to database `piki`.
- PostgreSQL image exposes pgvector as an available extension.
- API `/health/live`: `200`, process `ok`.
- API `/health/ready`: `200`, PostgreSQL and Redis `reachable`.
- API, worker, PostgreSQL, Redis, and n8n: healthy in Compose; migration job exited `0`.
- Worker stop: exit `0` and structured `worker_stopped` log; restart returned healthy.
- `scripts/smoke-stage2.sh`: passed with full stack including n8n.
- Production `deploy/stack.yml`: rendered successfully to 238 lines through `docker stack config`; no local secret values appeared.
- Final quality gate: Ruff passed, strict MyPy passed for 12 source files, Pytest 14 passed.

## 2026-07-16 - Stage 3 / BuenPick Client And Typed Tools

Implemented and inspected:

- Strict API models for search, detail, commerce, fulfillment, pickup, and customer-owned orders.
- Async HTTPX adapter with bearer auth, bounded timeouts/retries, safe status mapping, and
  production-host rejection by default.
- Explicit ARS-cent formatting and locally disabled checkout.
- Typed tools for search, pick detail, commerce, owned order, and image evidence. A source scan
  found no WhatsApp, Meta, `send_message`, or `send_image` behavior in the client/tool modules.

Contract and failure tests use `httpx.MockTransport` with the reserved host
`mock.buenpick.invalid`. The sole production URL text in the test tree is passed to a constructor
that is asserted to reject it before any request.

Commands:

```bash
.venv/bin/ruff check src/piki tests
.venv/bin/mypy src
.venv/bin/pytest -q
rg -n -i 'send_message|send_image|meta|whatsapp' \
  src/piki/tools src/piki/integrations/buenpick
```

Result:

- Ruff: all checks passed.
- Strict MyPy: no issues in 18 source files.
- Pytest: 33 passed.
- Contract coverage proves empty success, schema validation, pick `404`, commerce nullable fields,
  ownership preconditions, non-enumerating `401`, bounded retries, exhausted timeout, token
  non-disclosure, disabled checkout, cents formatting, and typed tool failures.

Docker commands and results:

```bash
<docker-desktop> compose build piki-api piki-worker
<docker-desktop> compose up -d --force-recreate migrate piki-api piki-worker
DOCKER_BIN='<docker-desktop>' bash scripts/smoke-stage2.sh
<docker-desktop> compose ps
```

- Image build passed and included the Stage 3 source package.
- The first recreation attempt used the nonexistent service name `migration` and failed before
  recreation; `docker compose config --services` showed the correct name `migrate`.
- Re-running with `migrate` completed the migration job and recreated API/worker.
- Smoke checks passed; API, worker, PostgreSQL/pgvector, Redis, and n8n all reported healthy.
- No request was made to `api.buenpick.com.ar`.

## 2026-07-16 - Stage 4 / Redis Active Pick

Implemented:

- Hashed state keys scoped by channel, channel account, and conversation.
- Frozen active-pick references containing identifiers and selection metadata, not mutable facts.
- Atomic Redis TTL writes, explicit clear, corrupt-state removal, and typed unavailable outcomes.
- Resolver precedence for explicit references and mandatory BuenPick reconfirmation for inherited picks.
- Stale-context clear on API `404`; other upstream errors preserve context but return no commercial data.

Quality commands:

```bash
.venv/bin/ruff check src/piki tests
.venv/bin/mypy src
.venv/bin/pytest -q
```

Result: Ruff passed, strict MyPy passed for 20 source files, and 41 tests passed. Active-pick
tests cover isolation, hashed identities, controlled TTL expiry, explicit precedence, upstream
reconfirmation, stale clearing, corrupt state, and Redis failure behavior.

Real Redis validation used the rebuilt non-root Piki image on the internal Compose network:

```bash
<docker-desktop> compose build piki-api
<docker-desktop> run --rm -i --network piki_backend \
  piki-local:stage2 python - <active-pick-smoke-script>
```

Result: `real Redis active-pick isolation and TTL passed`. The script wrote a two-second reference
for conversation A, proved B was missing, waited for expiry, proved A was missing, and closed the
Redis client. No BuenPick or other external endpoint was called.

## 2026-07-16 - Stage 4 / Redis Locks And Deduplication

Implemented:

- Conversation locks use random owner tokens, `SET NX EX`, and atomic Lua compare-and-delete.
- Lock keys hash the complete conversation scope; bounded TTLs recover abandoned leases.
- Inbound message claims hash channel account plus provider message ID and use `SET NX EX`.
- Busy, duplicate, not-owner, and Redis-unavailable outcomes remain distinct.

Quality result: Ruff passed, strict MyPy passed for 21 source files, and 48 tests passed. Unit tests
prove cross-conversation lock isolation, wrong-owner protection, expiry recovery, account-scoped
deduplication, replay rejection, expiry, hidden external identifiers, and outage behavior.

Real Redis command pattern:

```bash
<docker-desktop> compose build piki-api
<docker-desktop> run --rm -i --network piki_backend \
  piki-local:stage2 python - <coordination-smoke-script>
```

Result: `real Redis lock ownership and message dedup passed`. The smoke acquired a lease, rejected a
second worker, rejected a foreign release token, released as owner, claimed one message, rejected
its replay, and accepted it after the two-second test TTL. No external API was called.

## 2026-07-16 - Stage 4 / Pending Actions

Implemented typed pending actions for selecting among at least two pick IDs and requesting ownership
proof for one order ID. State contains no prices, stock, customer phone, email, or proof value.
Conversation-scoped Redis writes have TTL; `GETDEL` provides atomic single-consumer continuation.

Quality result: Ruff passed, strict MyPy passed for 22 source files, and 54 tests passed. Tests prove
shape validation, isolation, expiry, one-time consumption, corrupt-state removal, hidden external
identifiers, and explicit outage results.

The rebuilt image then ran two concurrent `consume` calls against Redis 7.4: exactly one returned
`found` and one returned `missing`. A separate two-second write expired as expected. Result:
`real Redis pending-action atomic consume and TTL passed`. No external endpoint was called.

## 2026-07-16 - Stage 4 / Durable Persistence And Final Gate

Implemented:

- ORM mappings aligned to the existing `conversations` and `messages` migration.
- Async engine resource and one `AsyncSession` per context-managed unit of work.
- Transactional conversation upsert and durable message insert with unique replay protection.
- Conversation-ID-scoped recent history with bounded limits.

The rebuilt Piki image ran an integration script inside the Compose network. It created a unique
test account, persisted an inbound message, detected its replay in a second transaction, added a
second message and a separate conversation, proved isolated chronological histories, forced and
verified a rollback, deleted test records, and disposed the engine. Result:
`real PostgreSQL durable conversation, dedup, isolation, and rollback passed`.

Final commands:

```bash
.venv/bin/ruff check src/piki tests
.venv/bin/mypy src
.venv/bin/pytest -q
<docker-desktop> compose up -d --wait piki-api piki-worker n8n
DOCKER_BIN='<docker-desktop>' bash scripts/smoke-stage2.sh
<docker-desktop> compose ps
```

Results:

- Ruff passed; strict MyPy passed for 26 source files; 57 tests passed.
- A source scan found engine factories but no process-global `AsyncSession` construction.
- The first immediate smoke after recreation raced while API/worker health was `starting` and curl
  exited `56`; rerunning through `compose up --wait` waited for health correctly.
- API, worker, PostgreSQL/pgvector, Redis, and n8n reported healthy; migration exited successfully;
  full smoke passed.
- No BuenPick production or other external operational endpoint was called.

## 2026-07-16 - Stage 5 / Piki Evidence Renderer

Dependency verification used the official Jinja 3.1 documentation and PyPI release record before
pinning `jinja2==3.1.6`. The environment uses `PackageLoader`, `StrictUndefined`, explicit text
autoescape selection, and a custom JSON-string filter for all dynamic content.

Implemented one system prompt and one evidence template with these sections: `TAREA`, `CONSULTA`,
`DATOS CONFIRMADOS`, `DATOS NO DISPONIBLES`, `ACCIONES REALIZADAS`, `REGLAS DE REDACCIÓN`, and
`CONTROL`. Runtime assets contain Piki/BuenPick/food-rescue identity but no legacy brand, candy,
wholesale/retail, scraper, real pick, price, stock, commerce, schedule, or URL fixture.

Quality result: Ruff passed, strict MyPy passed for 28 source files, and 61 tests passed. Tests include
an exact golden render, explicit empty sections, heading-injection containment, identity/legacy
language invariants, and absence of fixture values from template source.

Packaging validation:

```bash
.venv/bin/pip wheel --no-deps --wheel-dir <clean-dir> .
unzip -l <wheel> | rg 'piki/prompts/(system_prompt|templates/evidence)'
<docker-desktop> compose build piki-api
<docker-desktop> run --rm piki-local:stage2 python -c '<render packaged assets>'
```

- Initial wheel inspection found the template twice because `force-include` duplicated Hatch's
  automatic package-data inclusion. Removing that override produced exactly one system prompt and
  one template entry.
- Container result: `packaged Piki prompt assets render passed`.
- No external operational API was called.

## 2026-07-16 - Stage 5 / Policy Registry

Added seven exhaustive policies: discovery, pick detail, commerce information, owned order status,
pick image, human handoff, and non-commercial BuenPick explanation. Each defines an explicit mode,
allowlisted tools, task, and route-specific rules. Model validation rejects commercial policies
using `NON_COMMERCIAL_LLM` or not requiring confirmed evidence.

Quality result: Ruff passed, strict MyPy passed for 29 source files, and 67 tests passed. Tests prove
registry exhaustiveness, evidence enforcement, exact `ContextPacket` construction, known/channel-
neutral tools, unsafe-policy rejection, and absence of legacy catalog language. No external API was
called.

## 2026-07-16 - Stage 5 / LLM Adapter, Grounding, And Final Gate

The provider adapter follows the current official Responses API shape: `instructions` is separate
from message `input`, `store` is false, no tools are supplied, and raw response parsing scans all
message `output_text` content instead of relying on the SDK-only `output_text` convenience field.
Model and API key have no runtime default.

Contract tests use only `llm.mock.invalid` through `httpx.MockTransport`. They prove request shape,
history ordering, auth without log disclosure, multi-item output parsing, bounded 429 retry, timeout,
safe HTTP error mapping, refusal, incomplete/empty/malformed output, and factory requirements. No
provider request was made.

Grounding tests prove:

- exact evidence-backed currency, quantity, time, and URL can pass;
- invented high-risk values are blocked;
- internal headings, trace markers, and raw references are blocked;
- unknown surprise-bag contents cannot be asserted;
- fallback contains only confirmed Internal API values and sanitizes control markers;
- deterministic, Jinja, Jinja+LLM, and non-commercial LLM paths are bounded.

Final result: Ruff passed, strict MyPy passed for 36 source files, and 93 tests passed. The rebuilt
image printed `packaged renderer and grounding validation passed`; API, worker, PostgreSQL/pgvector,
Redis, and n8n returned healthy after recreation; the full smoke script passed. Prompt-source scan
found only the one system prompt, one evidence template, renderer, and policy registry, with none of
the rejected legacy catalog terms. No external operational API was called.

## 2026-07-16 - Stage 6 / Meta Webhook Boundary

Official Meta documentation URLs were rechecked but returned `429`/fetch errors from this
environment. Implementation therefore stays within the already documented stable webhook contract
and is proven with local anonymized fixtures; no Meta endpoint was called.

Implemented GET verification, HMAC SHA-256 validation over exact POST bytes, strict-enough Meta raw
models, and channel-neutral normalized events. The route returns `401` for a bad signature, `400`
for invalid signed payloads, and `503` rather than acknowledging when durable ingress is absent.

Fixtures cover text, image metadata/caption, button reply, unsupported location, and sent,
delivered, read, and failed statuses with a provider error. Quality result after this slice: strict
MyPy passed for 39 source files and 101 tests passed; Ruff findings were limited to two explicitly
annotated inert fixture credentials and then cleared. No external endpoint was called.

## 2026-07-16 - Stage 6 / Meta Outbound Adapter

Implemented channel-neutral delivery contracts for text, image, up to three reply buttons, and
template name/language/body parameters. The Meta adapter sends only public image links and maps a
successful response to `accepted` only when a non-empty provider `wamid` exists.

Explicit Graph errors map to `failed` with provider code and no private response detail. Timeout,
network ambiguity, or malformed success maps to `unknown`; the adapter makes exactly one POST.
Quality result: strict MyPy passed for 40 source files and 112 tests passed. Contract tests use only
`graph.mock.invalid` and prove exact payloads, real link/caption mapping, templates, buttons, token
non-disclosure, local validation, explicit rejection, uncertain timeout, and no false success. No
Meta endpoint was called.

## 2026-07-16 - Stage 6 / Durable Delivery And Ingress

Migration `0002_delivery_status_events` adds append-only status history while the existing delivery
attempt row retains the latest known provider state. The delivery service claims one idempotency key
before calling Meta, returns persisted replay results without a second adapter call, records explicit
failure/uncertainty, and accepts only monotonic callback progress.

A real PostgreSQL integration run sent one locally mocked acceptance, replayed the same request with
one total adapter call, applied sent/delivered/read callbacks, discarded a duplicate callback, and
audited a late failed regression without replacing read. Alembic downgraded to `0001_core_records`,
proved the event table absent, and upgraded back to `0002_delivery_status_events` successfully.

Default webhook ingress now commits normalized messages through the conversation repository before
marking Redis. A real Redis/PostgreSQL integration run printed
`real Redis/PostgreSQL Meta ingress dedup and callback persistence passed`: first `wamid` accepted,
replay detected as duplicate, callback applied, callback replay detected, and a callback without an
attempt reported a retryable error. No external endpoint was called.

## 2026-07-16 - Stage 6 / Operational Configuration And Docker Gate

Meta App Secret, access token, and verify token support Docker secret files. Enabled ingress validates
its signing and challenge secrets during settings construction. Local Compose passes ignored `.env`
values; the production stack mounts three external Meta secrets and explicitly configures WABA,
Phone Number ID, Graph version, and ingress enablement. The owner guide now separates Meta setup from
n8n's future signed-event workflows.

Commands and results:

```bash
.venv/bin/ruff check src/piki tests migrations
.venv/bin/mypy src
.venv/bin/pytest -q
<docker-desktop> version
<docker-desktop> compose version
<docker-desktop> info
<docker-desktop> compose build piki-api piki-worker migrate
<docker-desktop> compose run --rm migrate
<docker-desktop> compose up -d --wait piki-api piki-worker n8n
DOCKER_BIN='<docker-desktop>' bash scripts/smoke-stage2.sh
```

- Ruff passed; strict MyPy passed for 43 source files; 117 tests passed.
- Docker Desktop 4.76.0, Engine 29.5.2, and Compose 5.1.4 were available.
- Migration completed; API, worker, PostgreSQL/pgvector, Redis, and n8n were healthy; smoke passed
  against revision `0002_delivery_status_events`.
- `/health/live`, `/health/ready`, and n8n `/healthz` returned `ok`.
- The first extra packaged-prompt command imported the nonexistent name `PromptRenderer` and failed.
  Inspection showed the real public class is `PromptAssets`; the corrected container command printed
  `packaged Piki prompt and Jinja renderer available`.
- The first `docker.exe stack config` attempt failed because inline WSL environment variables did not
  cross into the Windows process. Repeating from PowerShell rendered 259 lines with all Meta secret
  mounts and no published service port.
- No BuenPick production, Meta, LLM provider, or other external operational endpoint was called.

## 2026-07-16 - Stage 6 / Customer-Service Window

Delivery requests now carry explicit `open`, `closed`, or `unknown` window evidence. The Meta adapter
blocks text, image, and interactive payloads before HTTP unless the window is confirmed open;
templates remain eligible with a closed window. Successful provider states also require a real
provider message ID.

Ruff passed, strict MyPy passed for 43 source files, and 120 tests passed. Parameterized contract
tests prove both closed and unknown free-form requests make zero HTTP calls and return distinct safe
failure codes; the template payload test runs with a closed window. No external endpoint was called.

## 2026-07-16 - Stage 6 / Final Gate

A controlled FastAPI lifespan test replaced the owned-ingress factory, started and stopped the app,
and proved both the Meta ingress resource and readiness probes closed. Final quality result: Ruff
passed, strict MyPy passed for 43 source files, and 121 tests passed.

The image was rebuilt after the window and shutdown changes. API, worker, PostgreSQL/pgvector, Redis,
and n8n all reported healthy; migration `0002_delivery_status_events` was current; the full smoke
script passed. A command inside `piki-api` imported the packaged customer-window contract and Piki
prompt assets and printed `packaged Stage 6 contracts and Piki assets passed`. No external operational
endpoint was called. Every Stage 6 harness gate item is backed by a contract, unit, real local
Redis/PostgreSQL, or Docker test.

## 2026-07-16 - Stage 7 / Golden Harness And Greeting

Added `tests/golden/support.py`, which uses the production policy registry, ContextPacket builder,
packaged Jinja assets, ResponseComposer, ResponseEngine, and GroundingValidator with only a scripted
provider-neutral LLM boundary. G-001 proves the final greeting identifies Piki and BuenPick, expresses
food rescue, selects the non-commercial policy with no tools, performs exactly one composition, and
contains no legacy brand or internal pipeline markers.

The first targeted run failed during collection because `tests` was not a package; adding the test
package marker fixed the import. The next full gate found one Ruff import-order issue; Ruff applied its
deterministic fix. Final result: Ruff passed, strict MyPy passed for 43 source files, the greeting
golden passed, and 122 total tests passed. No external endpoint was called.

## 2026-07-16 - Stage 7 / Search Evidence Goldens

Added a runtime mapper from `ToolResult[PickSearchResponse]` to a strict evidence bundle. It formats
API integer cents with the existing ARS formatter, includes only current typed pick fields, and emits
a confirmed API absence for `items=[]`; tool failures remain unavailable data instead.

G-002 proves one anonymous BuenPick fixture flows through evidence/Jinja/composition/grounding with
`250000` cents rendered as `$2.500,00`, quantity 2, and no internal pick ID or unformatted original
price in user text. G-003 proves an empty response retains tool success, a succeeded action, no
unavailable/error state, and an honest suggestion to change the search.

Both targeted goldens passed. Ruff then fixed one import grouping mechanically. Final result: Ruff
passed, strict MyPy passed for 45 source files, and 124 tests passed. No external endpoint was called.

## 2026-07-16 - Stage 7 / Active Pick Image Goldens

Added `PickImagePreparer`, a narrow application use case over the existing active-pick resolver and
typed BuenPick image tool. It returns confirmed title/image evidence and a public URL without doing
channel delivery, or returns an explicit missing/stale/state/upstream/image failure.

G-005 proves an inherited pick is reconfirmed, the image tool reconfirms it again, the confirmed
images array wins over fallback image URL, deterministic response uses no LLM, and the active ID
remains internal. G-004 proves a BuenPick `404` before photo selection yields no media or confirmed
data, emits an honest rescue-market message, makes no second image lookup, and removes the Redis
reference.

Both targeted goldens passed. Ruff removed one unused import and normalized import order. Final
result: Ruff passed, strict MyPy passed for 47 source files, and 126 tests passed. No external
endpoint was called.

## 2026-07-16 - Stage 7 / Order And Upstream Failure Goldens

Extended the typed evidence mapper for owned orders. It includes only operational fields needed for
the answer and deliberately excludes ownership proof, phone/reference values, customer delivery
address/notes, and the internal order ID from user text.

G-010 proves confirmed `ready`, commerce, `$3.000,00`, and pickup code evidence pass through the real
response pipeline without those excluded fields. G-011 proves a shared unauthorized failure remains
non-enumerating, produces no confirmed evidence, and cannot build the commercial order policy packet.
G-012 proves a typed BuenPick timeout remains a failed action/unavailable datum and cannot enter the
commercial search pipeline.

All three targeted cases passed. Ruff passed, strict MyPy passed for 47 source files, and 129 tests
passed. No external endpoint was called.

## 2026-07-16 - Stage 7 / Response Observability

Added fixed lifecycle event/outcome contracts, null/structlog/recording sinks, and a timing observer.
The record schema has no arbitrary metadata or text fields: only trace ID, allowlisted component,
outcome, duration, optional error code, and evidence counts. Response composition now emits correlated
context, Jinja, LLM, and grounding events.

Tests prove the exact five-event success sequence, one shared trace, nonnegative timings, absence of
query/evidence text from serialized records, and a distinct `blocked` grounding event with
`unsupported_high_risk_fact`. Ruff passed, strict MyPy passed for 49 source files, and 131 tests
passed. No external endpoint was called.

## 2026-07-16 - Stage 7 / Tool And Delivery Observability

`BuenPickTools` now emits correlated start/finish events around each allowlisted operation, preserving
success/failure, measured duration, and typed client error code without query, identifier, or result
text. `IdempotentDeliveryService` measures the complete claim/adapter/persistence attempt and emits a
separate failure event for rejection or uncertainty.

Tests prove two tools share a trace while distinguishing success from timeout, all durations are
nonnegative, an accepted Meta POST produces only `delivery_attempted`, and a provider rejection emits
attempt plus failure with the provider code. No test or implementation maps acceptance to
`delivery_succeeded`; that event remains reserved for a durable delivered callback.

Targeted tool/delivery tests passed. Ruff passed, strict MyPy passed for 49 source files, and 134
tests passed. No external endpoint was called.

## 2026-07-16 - Stage 7 / Docker Checkpoint

A source scan of runtime prompt/evidence/use-case modules found no Delify, Delibot, candy, or legacy
wholesale/retail terms. The first long Docker build command did not complete the recreate sequence;
the existing services stayed healthy, but an explicit in-container import correctly failed with
`ModuleNotFoundError: piki.observability`. This prevented a false packaged-runtime claim.

The build was rerun to completion, API and worker were force-recreated, Compose waited for all
healthchecks, and the migration/smoke script passed at `0002_delivery_status_events`. An in-container
check then imported Stage 7 evidence, active-image use case, and observability modules and printed
`packaged Stage 7 evidence, use cases, and observability passed`. API, worker, PostgreSQL/pgvector,
Redis, and n8n all reported healthy. No external operational endpoint was called.

## 2026-07-17 - Legacy Operator Console Recovery Correction

The initial recovery map omitted a functional frontend present in both legacy extracts. Direct
inspection found slim markers for `frontend/index.html` at line 20464, `package.json` at 20485,
`ChatView.jsx` at 20605, `KanbanBoard.jsx` at 20916, `ProductSearchDialog.jsx` at 21668, the WebSocket
hook at 22084, and frontend services through 22254. The large extract contains the corresponding
frontend around lines 167976-170002.

`ChatView` loaded history, consumed `new_message` events, distinguished client/bot/agent messages,
and submitted manual agent replies. `KanbanBoard` loaded and moved local orders through
`CONSULTA_NUEVA`, `TOMANDO_PEDIDO`, `EN_REPARTO`, `FINALIZADO`, and `SOPORTE`. Backend message,
order-move, and WebSocket implementations corroborate that this was operational rather than a mock.

The map now classifies conversation triage, human chat, history, and real-time updates as recoverable.
Local order stages, product search, quotes/orders, unauthenticated raw WebSockets, and optimistic send
success are explicitly not recoverable Piki contracts. `docs/OPERATOR_CONSOLE_ARCHITECTURE.md`
defines the replacement boundary and staged delivery plan.

## 2026-07-17 - Stage 7 / Durable Handoff Foundation

Migration `0003_handoff_workflow` scopes idempotency to the conversation, adds a PostgreSQL partial
unique index allowing only one requested/claimed handoff, changes new conversation workflow state to
`piki_active`, and supports reversal to `0002_delivery_status_events`. `HandoffRepository` inserts or
converges on the open handoff and transitions the conversation to `needs_human` in the same unit of
work.

Commands and results:

```bash
.venv/bin/ruff check src/piki tests migrations
.venv/bin/mypy src
.venv/bin/pytest -q
<docker-desktop> compose build piki-api piki-worker migrate
<docker-desktop> compose run --rm migrate
<docker-desktop> compose run --rm migrate alembic downgrade 0002_delivery_status_events
<docker-desktop> compose run --rm migrate
<docker-desktop> compose up -d --force-recreate --wait piki-api piki-worker n8n
<docker-desktop> compose exec -T piki-api python -c <real-handoff-check>
DOCKER_BIN=<docker-desktop> bash scripts/smoke-stage2.sh
```

- Ruff passed; strict MyPy passed for 50 source files; all 135 tests passed.
- Alembic upgraded, downgraded, and upgraded again without error.
- The in-container PostgreSQL check printed `real PostgreSQL idempotent handoff and workflow
  transition passed`: replay and a competing key returned the original handoff, one row remained,
  and conversation state was `needs_human`.
- API, worker, PostgreSQL/pgvector, Redis, and n8n were healthy; smoke passed at
  `0003_handoff_workflow`.
- No BuenPick production, Meta, LLM provider, or other external operational endpoint was called.

## 2026-07-17 - Short Owner Checklist

Added `GUIA_PENDIENTES_DUENO.md` after checking the active Stage 7 status, Stage 9 gate,
`.env.example`, local Compose, production stack, and the detailed Meta/n8n owner guide. The short
checklist explicitly states that Piki is not complete, allows only account/value preparation now,
defers real n8n workflows until signed Stage 9 event contracts exist, and lists the final Meta and
end-to-end acceptance steps. No runtime or external platform was changed.

## 2026-07-17 - n8n Owner Quickstart

Read the required foundation documents, active Stage 7, Stage 9, current status, `.env.example`,
local Compose, `.gitignore`, and existing owner guides before editing. Added
`docs/operations/N8N_OWNER_QUICKSTART.md` to answer the owner-facing `.env` question directly:
`.env.example` remains the committed template, `.env` is the ignored local runtime file, and only the
local n8n values need to be filled now.

The guide keeps n8n limited to a healthy isolated service with an owner account until Stage 9
publishes signed/idempotent event APIs. It explicitly prohibits direct Meta, Piki database, BuenPick
database/API, chat response, Kanban move, and commercial-decision workflows. No runtime code,
secrets, Docker state, n8n workflows, or external services were changed.

## 2026-07-17 - n8n Persistent-State Owner Warning

Updated the short and detailed owner-facing guides after a real local recovery showed two normal
persistence properties: editing `.env` does not rotate the password of an existing PostgreSQL role,
and an initialized n8n data volume retains the encryption key used to protect credentials. The docs
now prohibit `docker compose down -v` as a repair step, require retaining one backed-up
`N8N_ENCRYPTION_KEY`, and direct the owner to inspect status and logs before changing persistent
state.

Safe validation used Docker Desktop Compose without reading or printing secret values. It reported
`piki-n8n-1` as `running` and `healthy`, published on port `5678`. The owner confirmed the admin
account exists and there are zero workflows; no n8n API, database, volume, `.env`, secret file,
runtime code, container, or external service was modified.

## 2026-07-17 - Productive Meta Readiness Without Activation

Verified `/secrets/` and `/secret/` root exclusions before reading local credential files; no Git
repository exists yet, so the root `.gitignore` is the active future-commit protection. Scanning
reported only presence/absence. The productive WABA and Phone Number IDs matched the owner-confirmed
values, the long-lived access token had the expected shape, and a new 32-byte webhook verify token
was generated under the ignored `secrets/` directory. App ID and App Secret remain absent.

Three sanitized, read-only Graph `v25.0` calls returned HTTP 200: the productive WABA identity was
confirmed, its phone-number collection contained the expected productive Phone Number ID and not the
test Phone Number ID, and `/me/permissions` reported both `whatsapp_business_management` and
`whatsapp_business_messaging` granted. No response body, access token, secret, personal phone value,
or provider trace was recorded. No `POST` request was made.

Added configured-asset validation at the webhook boundary, an explicit local Compose override for
Docker secret files, and an opt-in production ingress flag. The merged local configuration reported
two secret mounts for API, one for worker, and `PIKI_META_INGRESS_ENABLED=false`. A one-off Piki
container constructed and closed the real Meta delivery adapter from the mounted token file without
calling `send`; it reported delivery configuration ready and ingress disabled. The production stack
parsed with App Secret and verify token file paths while retaining ingress disabled.

Targeted Meta/config tests passed after correcting one test that had inherited local `.env` IDs.
Final Ruff passed, strict MyPy passed for 50 source files, and the full test suite passed. Added cases
cover wrong challenge mode, altered signed HTTP body, signed events for an unexpected WABA/phone,
explicit Graph 400/503 failures, and required WABA/phone settings. No external operational endpoint
other than the three authorized Graph GETs was called.

The rebuilt image completed successfully. API and worker were force-recreated without the Meta
secret override; API, worker, PostgreSQL/pgvector, Redis, and the untouched n8n service all reported
healthy, and the complete smoke script passed at migration `0003_handoff_workflow`. In-container
checks reported Graph `v25.0` asset binding ready, direct Meta secrets absent, and ingress false. An
image filesystem check found no productive Meta or NVIDIA credential artifact under `/app`.

Final verified totals: Ruff passed, strict MyPy passed for 50 source files, and all 143 tests passed.
Inbound image handling remains typed, while explicit audio, document, video, and sticker cases prove
that unimplemented media is accepted as `unsupported` without download or commercial processing.
An exact-token scan reported zero matches outside the ignored `secrets/` directory. Because the
workspace is not yet a Git repository, `git check-ignore` cannot execute; root-anchored `/secrets/`
and `/secret/` rules are present and ready for repository initialization.

## 2026-07-17 - Durable Meta Callback Outcomes

Reconfirmed the ignored secret boundary before the safe presence scan. The productive ID file still
contains only WABA and Phone Number configuration; the separate long-lived access-token and webhook
verify-token files remain present. App ID and App Secret remain absent. No Graph request, message
send, Meta mutation, n8n workflow, or ingress activation occurred in this iteration.

Refactored callback application so lifecycle outcomes occur only after the database session exits
and commits. Tests prove exact `enter -> apply -> commit -> emit` order for delivered and failed,
zero outcomes for sent/read/duplicate/regression, and zero success when commit raises. G-013 proves a
Meta rejection remains failed on first attempt and idempotent replay, invokes the adapter once, and
never emits delivery success.

Commands and results:

```bash
.venv/bin/ruff check src/piki tests migrations
.venv/bin/mypy src
.venv/bin/pytest -q
<docker-desktop> compose build piki-api piki-worker migrate
<docker-desktop> compose up -d --force-recreate --wait piki-api piki-worker
<docker-desktop> compose exec -T piki-api python - <controlled-callback-check>
DOCKER_BIN=<docker-desktop> bash scripts/smoke-stage2.sh
```

- Ruff passed; strict MyPy passed for 50 source files; all 151 tests passed.
- The real PostgreSQL check reported callback apply, duplicate replay, post-commit success
  observation, and fixture cleanup passed.
- API, worker, PostgreSQL/pgvector, Redis, and untouched n8n were healthy; smoke passed at migration
  `0003_handoff_workflow`.
- The running API reported `PIKI_META_INGRESS_ENABLED=false`.

## 2026-07-17 - Meta App Identity And n8n Readiness Follow-up

Verified the root `/secrets/` ignore rule before scanning the newly referenced local file. Its
on-disk size and allowlisted labels showed only WABA ID and Phone Number ID; App ID and App Secret
were not present. A read-only Graph `v25.0` app lookup returned HTTP 200 and detected the App ID,
which was then mapped into the ignored local `.env`. App Secret cannot be derived and remains the
only missing Meta credential.

The first local HTTP challenge preflight caused the test HTTP logger to include the verify token in
its query string. That token had never been registered with Meta; it was immediately replaced with a
new 32-byte random value. A second in-container check avoided HTTP logging and reported App ID,
access token, and replacement verify token present, App Secret missing, the challenge comparison
contract passed, and ingress false. No message send, Meta mutation, DNS, Cloudflare, Dokploy, or
webhook-panel action occurred.

Docker Compose reported n8n healthy. A read-only count in its isolated PostgreSQL database returned
zero workflows. No n8n configuration state or credential was changed: the base service is ready,
while productive workflow creation remains gated on Stage 9 signed/idempotent event APIs.

The targeted Settings and Meta webhook suite passed all 21 tests. API, worker, and n8n remained
healthy after the local configuration change.

## 2026-07-18 - Productive Meta Secret Completion Without Activation

The root `/secrets/` ignore rule was confirmed before reading the owner addendum. A label-only scan
detected App ID and App Secret without rendering either value. The App ID matched the previously
Graph-confirmed local setting. The App Secret was written only to the ignored
`secrets/meta_app_secret.txt` file and mounted into `piki-api` through
`PIKI_META_APP_SECRET_FILE`; the access token and verify token remain file-mounted. The merged
Compose model parsed successfully and the container reported all Meta settings present with ingress
false.

An authorized read-only Graph `v25.0` preflight used `appsecret_proof`. App identity and productive
WABA returned HTTP 200, the configured productive phone returned `CONNECTED`, and
`whatsapp_business_management` plus `whatsapp_business_messaging` remained granted. No `/messages`
request, message send, asset mutation, webhook registration, DNS change, deployment, publication,
or ingress activation occurred.

A synthetic payload was HMAC-signed inside a one-off container using the mounted App Secret and
posted to the local FastAPI endpoint with ingress enabled only for that process. PostgreSQL accepted
the first inbound message, the replay was classified as duplicate, Redis coordination participated,
and the controlled PostgreSQL/Redis fixture cleanup passed. The normal running API subsequently
reported ingress false.

Reproducible results:

```text
docker compose -f docker-compose.yml -f compose.meta-local.yml config --quiet
container Settings preflight: all required Meta values present; ingress=false
Graph read-only appsecret_proof preflight: app/WABA/phone HTTP 200; phone CONNECTED; both permissions granted
synthetic signed POST: first=PASSED; duplicate=PASSED; cleanup=PASSED
.venv/bin/ruff check .: passed
.venv/bin/mypy src: passed for 50 source files
.venv/bin/pytest -q: 151 passed
DOCKER_BIN=<Docker Desktop CLI> ./scripts/smoke-stage2.sh: passed
n8n health: healthy; productive workflow count: 0
running piki-api ingress: false
exact-value workspace scan outside secrets/: no matches
exact-value current Compose log scan: no matches
```

n8n state was not modified. Its healthy service, existing administrator, isolated database, and
zero-workflow baseline are ready; productive workflows remain correctly gated on Stage 9 signed and
idempotent Piki event contracts.

## 2026-07-18 - Stage 7 / Conversational Vertical And Local Console

Implemented a channel-neutral conversation orchestrator over the real Redis lock, PostgreSQL
conversation history, deterministic intent policy, optional typed BuenPick tools, ContextPacket,
packaged Jinja, LLM composition, and blocking grounding. Search fails closed when the BuenPick token
is absent; no model is allowed to invent current picks, price, stock, or availability.

Added an NVIDIA NIM Chat Completions adapter behind the existing provider-neutral LLM contract. Its
ignored file secret resolves locally and the runtime uses `z-ai/glm-5.2`. Added an opt-in same-origin
chat API plus responsive Piki console. The console was inspected at desktop and mobile viewports;
browser automation found no console error or horizontal overflow and completed a real response.

Real HTTP proof against the rebuilt API created a greeting response and reloaded two durable turns
with roles `user` and `assistant`. The LLM attempted an evidence-free current-availability statement,
so grounding blocked it and returned Piki's safe factual fallback. This was an expected safety
result, not a provider outage. Controlled HTTP and browser fixtures were removed.

Added the four remaining harness goldens: durable handoff, conversation isolation, prompt injection,
and unavailable surprise-bag contents. All fourteen Stage 7 scenarios now have executable coverage.

## 2026-07-18 - Stage 7 / Durable Meta Processing Outbox

Migration `0004_message_processing_outbox` adds pending/processing/completed/failed state, bounded
attempt counts, claim and retry timestamps, and safe error codes to durable inbound messages. The
worker claims ready messages with `FOR UPDATE SKIP LOCKED`, recovers stale claims, invokes the shared
orchestrator, and calls the existing idempotent official Meta delivery service. Webhook receipt and
conversation processing are separate.

The migration completed a real PostgreSQL downgrade to `0003_handoff_workflow` and upgrade back to
head. A one-off worker integration used real PostgreSQL, Redis, Jinja, grounding, and NVIDIA NIM but
replaced only the final Meta adapter with a local fake. One queued inbound became one durable
outbound and one delivery attempt with state `accepted`; the second poll found no work, the fake was
called once, and no row claimed `delivered`. The fixture cleanup passed. No real `/messages` request
was made.

Final reproducible results:

```text
docker compose ... build piki-api: passed
docker compose ... up -d --force-recreate --wait: API, worker, PostgreSQL, Redis, n8n healthy
alembic downgrade 0003_handoff_workflow: passed
alembic upgrade head: passed; head=0004_message_processing_outbox
processing proof: completed; outbound=1; delivery attempts=1; accepted=1; delivered=0; replay empty
real HTTP chat proof: nonempty greeting; history turns=2; fixture cleanup=0
Playwright desktop/mobile: response present; console errors=0; horizontal overflow=false
.venv/bin/ruff check .: passed
.venv/bin/mypy src: passed for 60 source files
.venv/bin/pytest: 163 passed
DOCKER_BIN=<Docker Desktop CLI> ./scripts/smoke-stage2.sh: passed
local merged Compose config: passed; production stack config: passed
GET /console: passed; GET /health/ready: passed
```

The first shell-only final-chat reporting attempt used an incompatible Windows Python shim and an
unsupported psql variable form, so its reporting/cleanup commands failed after the HTTP request.
The corrected command used `.venv/bin/python`, removed every controlled `final-chat-proof-*` row,
reran the proof successfully, and confirmed zero remaining fixtures.

Normal local flags remain `PIKI_META_INGRESS_ENABLED=false` and
`PIKI_CONVERSATION_WORKER_ENABLED=false`. n8n remains healthy with its existing administrator and
zero production workflows. No DNS, Cloudflare, Dokploy, Meta webhook, Meta app publication, Meta
asset, or real recipient was modified.

The final sanitized secret preflight checked four exact current credential values without printing
them. It found zero matches outside ignored local configuration, zero matches in current Compose
logs, and zero matches in the rebuilt image application/package files. Both `/secrets/` and
`/secret/` are present in `.gitignore`; this workspace still has no `.git` repository.

## 2026-07-18 - BuenPick Internal Token Mounted Safely

The owner-provided WSL token source was verified as present and non-empty without rendering its
contents. It was copied to the ignored `secrets/buenpick_internal_api_token.txt` and mounted into
both local Piki services as `/run/secrets/buenpick_internal_api_token`. Because the workspace is on
Windows-mounted `/mnt/c`, DrvFS does not reliably preserve Linux file modes; the protected canonical
source remains `/home/juan/.secrets/buenpick/delibot_internal_api_token.txt`, while `.gitignore` and
the Docker secret mount protect the repo-side operational copy. The merged Compose model parsed, API
and worker were recreated healthy, the container reported the secret mount as non-empty, and
`buenpick_api_configured=true`.

`PIKI_BUENPICK_ALLOW_PRODUCTION` remains `false`, so the token's presence does not trigger live
BuenPick calls from the local console. No token value was printed, committed, logged, or sent to the
API during this step.

## 2026-07-18 - Explicit Local Production Test Profile Activated

The owner authorized a real WhatsApp test from another number. Added
`compose.prod-local.yml` as an explicit, reversible override and started it over the base, Meta, and
AI Compose files. The profile sets BuenPick production access, Meta ingress, conversation runtime,
and the durable conversation worker to `true`; it does not send anything by itself.

Preflight before activation found zero pending or processing inbound messages. After recreation,
API and worker healthchecks passed, the worker reported `worker_started`, both BuenPick and Meta
secret mounts were present, and the normal readiness endpoint remained healthy. No Meta message was
sent by Piki during activation.

The real BuenPick read-only preflight returned HTTP `200` for health and for pick searches with an
empty query plus `pan`, `pizza`, `bolsa`, and `rescate`; every response contained `items=0` and
`total=0`. The documented API exposes commerce detail only as `GET /commerces/{commerce_id}`; the
undocumented collection path `/commerces` returned `404`, so commerce availability cannot be asserted
without a valid commerce ID. No BuenPick mutation or order operation was attempted.

Meta still needs a public HTTPS route to this local API. `localhost:8000` is not reachable from
Meta's servers; use an already-authorized tunnel/proxy or deploy the public callback before sending
the WhatsApp test.

## 2026-07-18 - Real WhatsApp Test Diagnostic

The owner sent a real WhatsApp message while the explicit local production profile was active. No
inbound row was created, no processing job was pending, and API/worker logs contained only health
checks plus worker startup; no webhook POST reached Piki. DNS lookup for `piki-api.buenpick.com.ar`
failed from the local environment. A sanitized read-only Graph query returned WABA
`subscribed_apps` count `0` and no subscribed `messages` field. Therefore the failure occurred before
Piki: Meta has no public callback route and the WABA is not subscribed to the app webhook.

No outbound message, Meta mutation, or database mutation was performed during diagnosis.

## 2026-07-18 - GitHub Repository Baseline And Secret Guard

Reverted the temporary local production override to the safe local profile: Meta ingress and the
conversation worker are false, while API, worker, PostgreSQL, Redis, and n8n remain healthy. No
volumes were removed and no data was deleted.

Initialized an empty Git repository on branch `main` without adding a remote or creating a commit.
Added `README.md`, `SECURITY.md`, `.gitattributes`, and a GitHub Actions quality workflow. Expanded
`.gitignore` for root and nested secret directories, environment files, token/secret/API-key
filenames, private key formats, databases, logs, caches, Terraform state, and local artifacts.

`git add --dry-run .` listed application/docs/tests only; `secrets/`, `.env`, and `.artifacts/` were
ignored. Safe and production Compose models parsed. GitHub CI YAML parsed. Ruff, strict MyPy over 60
source files, all 163 tests, and the Docker smoke gate passed again. No secret value was printed or
staged.
