#!/usr/bin/env sh
set -eu

DOCKER_BIN=${DOCKER_BIN:-docker}
compose() {
  "$DOCKER_BIN" compose "$@"
}

compose ps
curl --fail --silent http://127.0.0.1:${PIKI_API_PORT:-8000}/health/live >/dev/null
curl --fail --silent http://127.0.0.1:${PIKI_API_PORT:-8000}/health/ready >/dev/null
compose exec -T postgres psql \
  --username "${POSTGRES_USER:-piki}" \
  --dbname "${POSTGRES_DB:-piki}" \
  --tuples-only \
  --command "SELECT version_num FROM alembic_version;" | grep -q 0004_message_processing_outbox
compose exec -T postgres psql \
  --username "${POSTGRES_USER:-piki}" \
  --dbname "${POSTGRES_DB:-piki}" \
  --tuples-only \
  --command "SELECT default_version FROM pg_available_extensions WHERE name = 'vector';" | grep -q .
compose exec -T piki-worker piki-worker --check
if [ "${SKIP_N8N:-0}" != "1" ]; then
  curl --fail --silent http://127.0.0.1:${N8N_PORT:-5678}/healthz >/dev/null
fi

printf '%s\n' "Stage 2 smoke checks passed"
