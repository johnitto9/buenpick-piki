# Owner Guide: Meta WhatsApp And n8n

This checklist separates owner-controlled platform work from Piki implementation. Do not paste real secrets into issues, chat, screenshots, or repository files.

## Meta WhatsApp Cloud API

Current productive-asset status and the exact Dokploy/Cloudflare/Meta handoff are maintained in
`docs/operations/META_PRODUCTION_HANDOFF.md`. It contains presence states only, never credentials.

### You Can Prepare Now

1. Choose or create the Meta Business Portfolio that owns BuenPick.
2. Create a Business-type Meta app and add the WhatsApp product.
3. Register the production phone number or keep Meta's test number for initial integration.
4. Record privately: Meta App ID, WhatsApp Business Account ID, Phone Number ID, and the intended display name.
5. Complete business verification and display-name review when Meta requires them.
6. Decide the public HTTPS host for Piki, for example `piki-api.<your-domain>`.
7. Reserve the callback path `https://<host>/webhooks/meta/whatsapp`.
8. Generate two independent random values: webhook verify token and n8n encryption key.

Official references:

- Cloud API getting started: <https://developers.facebook.com/docs/whatsapp/cloud-api/get-started>
- Webhooks: <https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks>

### Configure The Stage 6 Webhook

1. In Meta Business settings, create a dedicated system user for Piki and assign the BuenPick app and WhatsApp Business Account assets.
2. Generate its access token with only `whatsapp_business_messaging` and `whatsapp_business_management`. Record the expiry/rotation policy shown by Meta.
3. In the app's WhatsApp configuration, set callback URL `https://<piki-host>/webhooks/meta/whatsapp` and the independently generated verify token.
4. Subscribe the app/WABA to the `messages` webhook field. The same field carries inbound messages and delivery status callbacks.
5. Read the currently supported Graph version from Meta and set it explicitly; Piki intentionally has no version default.
6. Run migrations through `0004_message_processing_outbox` before enabling ingress.
7. Mount `meta_app_secret`, `meta_access_token`, and `meta_webhook_verify_token` as Dokploy/Swarm secrets. Set Phone Number ID, WABA ID, and Graph API version as environment values.
8. Set `PIKI_META_INGRESS_ENABLED=true` only after PostgreSQL and Redis are ready and the secrets are mounted.
9. Complete Meta's challenge. A wrong token must return `403`; a correct token returns the challenge as plain text.
10. Send one inbound message twice using Meta's retry/test facilities. PostgreSQL must contain one message and the second request must report a duplicate.
11. Send one outbound text and one real pick image. The initial API result must be `accepted`; wait for separate `sent`, `delivered`, and `read` callbacks.
12. Force a rejected recipient/template test and confirm the attempt is `failed`, never `delivered`. Force a timeout only in staging and confirm it remains `unknown` without automatic resend.

The local Compose stack accepts direct `PIKI_META_*` values from the ignored `.env`. The production
stack uses secret files for App Secret, access token, and verify token. Do not enable ingress in the
public Meta app until its callback URL has valid HTTPS and the current image passed smoke checks.

### Utility Templates And The Service Window

1. Create only the initial utility templates needed for owned-order status and requested human follow-up.
2. Use neutral parameters; Piki supplies values from confirmed order evidence at delivery time.
3. Submit each template for Meta approval and store its exact approved name and language code.
4. Use free-form text only when Meta accepts it inside the active customer-service conversation window.
5. Outside that window, send an approved template. Do not emulate the window with local delivery success: Meta remains authoritative and any rejection is persisted.
6. Keep marketing templates and broadcast workflows outside Piki's initial scope.

### Deployment Values

```text
PIKI_META_PHONE_NUMBER_ID=<Meta phone number ID>
PIKI_META_WABA_ID=<WhatsApp Business Account ID>
PIKI_META_GRAPH_API_VERSION=<currently approved version>
PIKI_META_INGRESS_ENABLED=true
```

External secrets expected by `deploy/stack.yml`:

```text
meta_app_secret
meta_access_token
meta_webhook_verify_token
```

After deployment, check `/health/ready`, complete the Meta challenge, send the signed fixture/test
events, and inspect `delivery_attempts` plus `delivery_status_events`. Never use a successful health
check as evidence that a WhatsApp message was delivered.

### Acceptance Evidence To Save

- Webhook verification succeeds without logging the verify token.
- Invalid `X-Hub-Signature-256` is rejected.
- Duplicate `wamid` produces no duplicate response.
- Meta rejection is stored as `failed`, never `delivered`.
- Status callbacks update `accepted/sent/delivered/read/failed` independently.

### Operator Console Relationship

The local development chat at `/console` proves the shared conversation core but is not the operator
console. The future authenticated Piki operator console is another client of Piki, not another
WhatsApp integration.
An operator reply is submitted to Piki, persisted with an idempotency key, and sent through the same
official Meta delivery service. The console displays `accepted`, `failed`, or `unknown` from that
attempt and changes to `delivered` or `read` only after Piki persists Meta callbacks.

Claiming a conversation pauses Piki's automated replies. Closing a browser tab does not resume the
bot, resolve the handoff, or alter delivery state. Those are explicit server-side transitions.

## n8n

### You Can Prepare Now

1. Copy `.env.example` to the local ignored `.env` and replace all `change-me` values.
2. Generate `N8N_ENCRYPTION_KEY` once and back it up securely. Changing it later prevents n8n from decrypting stored credentials.
3. Open `http://localhost:5678` after the Compose stack is healthy and create the local owner account.
4. For production, choose a private editor host such as `n8n.<your-domain>` and configure HTTPS through Dokploy.
5. Keep n8n's database user isolated from the `piki` database. The Compose initialization already creates a separate `n8n` database and role.

Persistent-state warning: changing `N8N_DB_PASSWORD` or `N8N_ENCRYPTION_KEY` in `.env` does not
rewrite an already initialized PostgreSQL role or n8n data volume. Never regenerate the encryption
key after credentials exist, and never use `docker compose down -v` as a repair step. For an existing
environment, inspect `docker compose ps n8n` and `docker compose logs --tail=100 n8n` first; diagnose
an encryption-key or database-authentication mismatch before changing persistent state.

Official references:

- Docker installation: <https://docs.n8n.io/hosting/installation/docker/>
- Deployment environment variables: <https://docs.n8n.io/hosting/configuration/environment-variables/deployment/>

### Do After Piki Stage 9 Publishes Signed Event APIs

Create only these workflows:

1. Human handoff notification from a durable `needs_human` transition.
2. Order-status operational notification.
3. Daily operational summary.

Each workflow must consume signed, idempotent Piki events. n8n must not query Piki/BuenPick databases, call Meta directly, choose commercial facts, compose assistant answers, or store BuenPick API credentials.

The handoff workflow may notify an internal channel and link an authorized operator to the Piki
console. It must not claim the conversation, reply to the customer, move the Kanban card, or resolve
the handoff on its own.

### Production Checklist

1. Create the external Swarm secrets `n8n_db_password` and `n8n_encryption_key`; retain an offline copy of the encryption key.
2. Set `N8N_HOST` to the private editor hostname and terminate TLS at Dokploy's proxy.
3. Restrict editor access with the platform's network or identity controls. Do not expose the editor as Piki's public webhook.
4. Keep workflow credentials limited to the future signed Piki event endpoint and notification destinations.
5. Export reviewed workflows as versioned JSON before each production change. Do not export credential values.
6. Exercise each workflow twice with the same event ID and confirm one side effect.
7. Disable the workflow before rollback, restore the last reviewed JSON, then replay only events whose idempotency state is known.

Verified 2026-07-17: local n8n is healthy at `http://localhost:5678`, its owner account exists, and it
has zero production workflows. This is the correct current state. Meta calls Piki directly; n8n is
not in the conversational delivery path.

## Values Piki Will Eventually Need

| Value | Owner/source | Needed stage |
|---|---|---:|
| BuenPick internal bearer token | BuenPick/Dokploy | 3 |
| LLM provider, model, API key | Product/engineering | 5 |
| Meta App ID and App Secret | Meta app dashboard | 6 |
| WABA ID and Phone Number ID | WhatsApp setup | 6 |
| Permanent system-user token | Meta Business settings | 6 |
| Webhook verify token | Owner-generated | 6 |
| Public API domain and TLS | DNS/Dokploy | 6/9 |
| n8n encryption key and editor domain | Owner-generated/DNS | 9 |

### BuenPick Token Handoff

The Internal API contract says the existing production token is managed in Dokploy for the
`bp-api` service (with a protected VPS copy). Treat that secret as the source of truth: ask the
BuenPick backend owner or read it through Dokploy's secret manager without printing it. Do not create
a second token unless the backend owner is deliberately rotating the current one, because both
services must change together.

For Piki, mount the coordinated value as the external secret `buenpick_internal_api_token` and set
`PIKI_BUENPICK_INTERNAL_API_TOKEN_FILE=/run/secrets/buenpick_internal_api_token`. The client uses
Bearer authentication against `https://api.buenpick.com.ar/internal/v1`; a read-only
`GET /picks/search` is the first authorized preflight. Keep the token out of `.env.example`, logs,
screenshots, and documentation.
