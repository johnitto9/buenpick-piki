# Etapa 9 — n8n mínimo y producción

## n8n

Solo:

1. handoff humano;
2. estado de orden;
3. resumen diario.

n8n usa APIs y eventos. No DB. No razonamiento. No Meta directo.

## Producción

- Docker final;
- migrations;
- secrets;
- health/readiness;
- rate limits;
- backups;
- feature flags;
- smoke manual;
- runbooks;
- rollback;
- métricas mínimas.

## Gate

- workflows versionados;
- eventos firmados e idempotentes;
- n8n acotado;
- despliegue reproducible;
- secretos fuera del repo;
- smoke documentado;
- rollback;
- fallos de Meta/BuenPick observables;
- proyecto completo conforme a los cuatro documentos fundacionales.

## Criterios prod-ready

- imágenes multistage;
- usuario no root cuando corresponda;
- servicios internos no expuestos públicamente;
- health/readiness;
- graceful shutdown;
- restart policy;
- migrations y rollback;
- backups de PostgreSQL;
- persistencia de Redis según necesidad;
- secretos gestionados fuera de imágenes;
- variables documentadas;
- límites de CPU/memoria;
- logs estructurados;
- trazas correlacionadas;
- despliegue reproducible en Dokploy/Swarm;
- smoke test post-deploy;
- rollback documentado.
