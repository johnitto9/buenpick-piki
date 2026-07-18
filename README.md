# Piki

Piki is BuenPick's evidence-first conversational assistant for rescuing surplus food from active
businesses. It keeps BuenPick's Internal API as the only source of truth for picks, prices, stock,
availability, commerce data, and orders.

## Local development

The safe local profile runs PostgreSQL + pgvector, Redis, Piki API, worker, n8n, and an opt-in chat
console:

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.meta-local.yml \
  -f compose.ai-local.yml \
  up -d --build --wait
```

Open `http://localhost:8000/console`. n8n is at `http://localhost:5678`.

The explicit `compose.prod-local.yml` profile enables real BuenPick reads and real Meta inbound/reply
processing. Use it only for an authorized test with a public HTTPS callback; it is intentionally not
part of the default command.

## Architecture

```text
Meta webhook -> durable PostgreSQL inbound -> Redis coordination -> policy/tools
-> BuenPick evidence -> Jinja ContextPacket -> GLM-5.2/NIM -> grounding
-> idempotent Meta delivery -> sent/delivered/read callbacks
```

Piki does not scrape, use unofficial WhatsApp bridges, access the BuenPick database, or let n8n
reason about commercial facts.

## Secrets

Never commit `.env`, `secrets/`, access tokens, App Secret, webhook verify tokens, API keys, private
keys, or local databases. `.gitignore` blocks those paths and secret-like filenames; `.dockerignore`
uses an allowlist so local secrets are excluded from image builds. Production values belong in
Dokploy/Swarm secrets.

See [SECURITY.md](SECURITY.md), [the owner guide](GUIA_PENDIENTES_DUENO.md), and
[the local chat guide](docs/operations/LOCAL_CHAT_QUICKSTART.md).

## Verification

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest
DOCKER_BIN="/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" ./scripts/smoke-stage2.sh
```

The current implementation and gate evidence are tracked in `PIKI_STATUS.md` and
`PIKI_EVIDENCE.md`.
