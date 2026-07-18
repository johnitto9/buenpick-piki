#!/bin/sh
set -eu

if [ -n "${N8N_DB_PASSWORD_FILE:-}" ]; then
  N8N_DB_PASSWORD=$(cat "$N8N_DB_PASSWORD_FILE")
fi

if [ -z "${N8N_DB_PASSWORD:-}" ]; then
  echo "N8N_DB_PASSWORD is required" >&2
  exit 1
fi

psql --set=ON_ERROR_STOP=1 \
  --set=n8n_password="$N8N_DB_PASSWORD" \
  --set=piki_database="$POSTGRES_DB" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE n8n LOGIN PASSWORD %L', :'n8n_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'n8n') \gexec
CREATE DATABASE n8n OWNER n8n;
REVOKE CONNECT ON DATABASE :"piki_database" FROM PUBLIC;
SQL
