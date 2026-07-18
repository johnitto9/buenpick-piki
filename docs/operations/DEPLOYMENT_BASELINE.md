# Deployment Baseline

## Local Development

```bash
cp .env.example .env
docker compose up --build -d
./scripts/smoke-stage2.sh
```

Only `piki-api:8000` and `n8n:5678` are published locally. PostgreSQL and Redis are reachable only on the Compose backend network.

## Production Preflight

1. Build and push `Dockerfile` with an immutable tag or digest.
2. Create Swarm/Dokploy secrets: `postgres_password`, `n8n_db_password`, `n8n_encryption_key`,
   `piki_database_url`, `meta_app_secret`, `meta_access_token`,
   `meta_webhook_verify_token`, `llm_api_key`, and `buenpick_internal_api_token`.
3. Ensure the `piki_database_url` secret contains a complete SQLAlchemy URL using the `postgresql+psycopg` driver.
4. Label the persistent-data node: `docker node update --label-add piki.data=true <node>`.
5. Create the proxy overlay network referenced by `PIKI_EDGE_NETWORK`.
6. Back up PostgreSQL and the n8n encryption key before every schema or n8n upgrade.
7. Run the migration image once before updating API/worker services:

```bash
docker service create --name piki-migrate-<release> \
  --mode replicated-job --restart-condition none \
  --network <backend-network> \
  --secret source=piki_database_url,target=piki_database_url \
  -e PIKI_DATABASE_URL_FILE=/run/secrets/piki_database_url \
  <immutable-piki-image> alembic upgrade head
```

Wait for the job to complete successfully, inspect its logs, confirm the schema is at
`0004_message_processing_outbox`, and remove the completed service. The exact one-off workflow may
be wrapped by Dokploy. Do not deploy the API against an unapplied schema.

## Stack Deployment

```bash
PIKI_IMAGE=<registry>/piki@sha256:<digest> \
PIKI_EDGE_NETWORK=<proxy-overlay> \
N8N_HOST=<private-n8n-host> \
docker stack deploy --with-registry-auth -c deploy/stack.yml piki
```

Dokploy should route the public Meta webhook host only to `piki-api:8000`. Restrict the n8n editor host with authentication and network policy. PostgreSQL and Redis have no published ports.

## Backup

PostgreSQL contains both isolated databases and must be backed up in two files:

```bash
docker exec <postgres-container> pg_dump -Fc -U piki piki > piki.dump
docker exec <postgres-container> pg_dump -Fc -U n8n n8n > n8n.dump
```

Also back up the external `n8n_encryption_key`; an n8n database restore without the matching key cannot decrypt credentials. Redis persistence is operational cache/state, not the durable source of conversation truth.

## Restore Drill

Restore into empty databases with the matching application versions:

```bash
pg_restore --clean --if-exists --no-owner -U piki -d piki piki.dump
pg_restore --clean --if-exists --no-owner -U n8n -d n8n n8n.dump
```

Then run migrations, start one API replica, verify `/health/live` and `/health/ready`, test one non-production conversation, and only then restore normal replica counts.

## Rollback

1. Stop rollout if readiness or smoke checks fail.
2. Use Swarm service rollback for application images.
3. Database rollback is migration-specific. Migrations through `0004_message_processing_outbox`
   have a tested local downgrade/upgrade path, but production data requires a backup-first decision
   before any destructive downgrade.
4. Never roll application code back across an incompatible schema without the documented migration path.
5. Confirm Meta delivery failures remain visible after rollback.
