# Security Notes

## Never commit

- `.env` and any environment file containing real values.
- Everything under `secrets/` or `secret/`.
- Meta access tokens, App Secret, webhook verify tokens, NVIDIA/BuenPick API keys.
- Private keys, certificates with private material, database dumps, local volumes, logs, and
  conversation exports.

The repository `.gitignore` and Docker build allowlist are defense-in-depth, not a replacement for a
secret manager. If a secret is ever committed, revoke/rotate it immediately; deleting the file is
not enough because Git history retains it.

## Runtime handling

Use Docker/Dokploy/Swarm secrets and `*_FILE` settings in production. Keep Meta ingress and the
conversation worker disabled until the public callback, credentials, and rollback plan are ready.
Piki never treats Meta `accepted` as `delivered`.

## Reporting

Do not paste secret values, full phone numbers, access tokens, raw provider payloads, or customer
messages into issues, logs, screenshots, or support chats. Report only presence/absence, status
codes, counts, and redacted error codes.
