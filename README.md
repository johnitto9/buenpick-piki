# Piki

### El asistente oficial de BuenPick para rescatar alimentos, con evidencia antes que lenguaje.

Piki es el sistema conversacional de BuenPick. Ayuda a las personas a encontrar oportunidades de
rescate de alimentos en comercios activos, entender una compra, consultar un pedido propio y pedir
atención humana. Su regla más importante es también su frontera de seguridad:

> Primero representa la realidad confirmada. Después permite que el modelo la transforme en lenguaje.

Piki no duplica la lógica comercial de BuenPick. No scrapea, no accede a la base de datos de BuenPick,
no usa bridges no oficiales de WhatsApp y no permite que n8n decida hechos comerciales.

## Qué resuelve

- Conversaciones por WhatsApp Cloud API oficial de Meta y una consola local de desarrollo.
- Memoria conversacional durable y estado efímero aislado por canal, cuenta y conversación.
- Búsqueda tipada de picks, comercios, imágenes y pedidos a través de BuenPick Internal API.
- Evidencia estructurada con Jinja, policies explícitas y grounding validator.
- GLM-5.2 mediante NVIDIA NIM detrás de un puerto LLM intercambiable.
- Delivery idempotente con estados reales: `accepted`, `sent`, `delivered`, `read` y `failed`.
- Handoff humano durable y base para la futura consola operativa/Kanban.
- Docker Compose local y stack compatible con Dokploy/Swarm.

## Arquitectura de extremo a extremo

```text
WhatsApp Cloud API (Meta)
        │ webhook firmado, normalizado y deduplicado
        ▼
PostgreSQL: inbound durable + processing outbox
        │ claim FOR UPDATE SKIP LOCKED
        ▼
Redis: locks, replay hints, active pick, TTL state
        ▼
Intent / policy / typed tools
        │
        ├── BuenPick Internal API (única verdad operacional)
        │       picks, stock, precios, comercios, pedidos
        │
        ▼
Evidence mapper → ContextPacket → Jinja inteligente
        ▼
System prompt + reglas + conversación → GLM-5.2/NIM
        ▼
Grounding validator
        │  bloquea claims sin evidencia, fugas internas y datos riesgosos
        ▼
PostgreSQL outbound + IdempotentDeliveryService
        ▼
Meta /messages → accepted
        ▼
Callbacks Meta → sent → delivered → read / failed
```

La aceptación HTTP de Meta no significa entrega. Piki solo registra `delivery_succeeded` después de
persistir un callback `delivered`.

## Componentes

| Componente | Responsabilidad | Fuente de verdad |
|---|---|---|
| `piki-api` | Healthchecks, webhook Meta, API de chat local y entrada durable | PostgreSQL/Redis |
| `piki-worker` | Reclamo del outbox, composición y delivery oficial | PostgreSQL + Meta |
| PostgreSQL 16 + pgvector | Conversaciones, mensajes, handoffs, delivery, migraciones y futura búsqueda semántica | Datos durables |
| Redis 7 | Locks, deduplicación rápida, TTL, active pick y coordinación | Estado efímero |
| BuenPick Internal API | Picks, precios, disponibilidad, comercios y pedidos | Verdad operacional externa |
| Jinja | Convierte datos tipados en evidencia legible | No contiene catálogo mutable |
| NVIDIA NIM / GLM-5.2 | Redacción conversacional controlada | Nunca inventa hechos |
| Meta WhatsApp Cloud API | Transporte oficial de inbound/outbound | Estado final de entrega |
| n8n | Futuros avisos y automatizaciones operativas | No razona ni responde chats |

## pgvector y búsqueda semántica

La imagen local usa `pgvector/pgvector:0.8.1-pg16-bookworm` desde el comienzo, pero pgvector no es
una fuente de stock ni disponibilidad. La Etapa 8 define su uso en tres índices separados:

- catálogo y candidatos semánticos;
- conocimiento estable de BuenPick/Piki;
- memoria conversacional acotada.

La regla es:

```text
pgvector encuentra candidatos
BuenPick reconfirma la realidad actual
Piki responde solo con la evidencia reconfirmada
```

La sincronización, embeddings reales, métricas de relevancia/latencia y rollback por feature flag
son el siguiente bloque de trabajo. Un embedding nunca puede convertir un pick vencido o agotado en
una respuesta disponible.

## BuenPick Internal API

Piki usa Bearer auth y un cliente tipado con timeouts, retries acotados, mapeo de errores y logs
redactados. Las operaciones permitidas son:

- `GET /picks/search` para resultados actuales;
- `GET /picks/{pick_id}` para reconfirmar un pick;
- `GET /commerces/{commerce_id}` para datos seguros del comercio;
- `GET /orders/{order_id}` únicamente con prueba de ownership;
- checkout interno deliberadamente deshabilitado.

Una búsqueda vacía (`items: []`) es una respuesta válida, no un error. Piki no completa precios,
stock, horarios ni contenidos de bolsas sorpresa con conocimiento del modelo.

## LLM, Jinja y grounding

El modelo no recibe objetos arbitrarios ni acceso a tools. El pipeline construye un `ContextPacket`
tipado con:

```text
TAREA
CONSULTA
DATOS CONFIRMADOS
DATOS NO DISPONIBLES
ACCIONES REALIZADAS
REGLAS DE REDACCIÓN
```

Jinja es un transformador de evidencia, no una base de conocimiento ni una respuesta hardcodeada.
El grounding bloquea lenguaje comercial no sustentado, referencias internas, instrucciones de prompt
injection y falsos estados de delivery. Si el proveedor falla, Piki usa un fallback factual o una
respuesta segura; nunca simula éxito.

## Docker local

### Perfil seguro de desarrollo

Este es el perfil recomendado para trabajar sin tráfico productivo:

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.meta-local.yml \
  -f compose.ai-local.yml \
  up -d --build --wait
```

Servicios y URLs:

```text
Piki console: http://localhost:8000/console
Readiness:     http://localhost:8000/health/ready
n8n:           http://localhost:5678
```

Este perfil deja Meta ingress y el worker de WhatsApp apagados. La consola permite probar saludo,
explicación de BuenPick, historial y handoff. El acceso productivo a BuenPick se protege con
`PIKI_BUENPICK_ALLOW_PRODUCTION=false`.

### Perfil productivo local, solo autorizado

`compose.prod-local.yml` activa consultas reales a BuenPick, ingress Meta y el worker de respuestas.
Usalo únicamente con un destinatario de prueba autorizado y un callback HTTPS público que enrute a
este equipo:

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.meta-local.yml \
  -f compose.ai-local.yml \
  -f compose.prod-local.yml \
  up -d --build --wait
```

Meta no puede alcanzar `localhost` directamente. Antes de enviar un WhatsApp real hay que configurar
el challenge, el verify token y la suscripción WABA al campo `messages`.

Para volver al perfil seguro, levantá nuevamente solo los tres primeros archivos. Nunca uses
`docker compose down -v`: los volúmenes contienen PostgreSQL y el estado cifrado de n8n.

## Variables y secretos

`.env.example` es una plantilla. `.env` es local e ignorado. En producción se prefieren secretos
Docker/Dokploy/Swarm mediante variantes `*_FILE`:

```text
PIKI_META_APP_SECRET_FILE
PIKI_META_ACCESS_TOKEN_FILE
PIKI_META_WEBHOOK_VERIFY_TOKEN_FILE
PIKI_LLM_API_KEY_FILE
PIKI_BUENPICK_INTERNAL_API_TOKEN_FILE
```

Nunca se versionan `secrets/`, tokens, App Secret, claves NVIDIA, claves privadas, dumps, logs ni
credenciales de n8n. El `.dockerignore` usa una allowlist de build para que los secretos locales no
entren en la imagen. Más detalles: [SECURITY.md](SECURITY.md).

## n8n

n8n es un consumidor de eventos, no parte del razonamiento conversacional. Sus futuros workflows
permitidos son:

1. Aviso cuando una conversación pasa a `needs_human`.
2. Notificación operativa de cambios de orden.
3. Resumen diario.

n8n no llama a Meta, no consulta PostgreSQL/BuenPick, no decide disponibilidad y no responde al
cliente. El entorno local actual tiene administrador creado y cero workflows productivos.

## Observabilidad y entrega

Los eventos estructurados están allowlisteados y correlacionados por `trace_id`. Registran etapa,
resultado, latencia, error sanitizado y conteos de evidencia, pero no mensajes completos, tokens,
teléfonos, payloads crudos ni datos comerciales innecesarios.

La entrega se persiste por idempotency key. Los replays de Meta no crean conversaciones ni mensajes
duplicados. Los callbacks avanzan monotónicamente y los retrocesos quedan auditados sin corromper el
estado actual.

## Tests y gates

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest

DOCKER_BIN="/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" \
  ./scripts/smoke-stage2.sh
```

La cobertura incluye contratos Meta/BuenPick/LLM, webhooks firmados, delivery, fallos, deduplicación,
golden conversations, prompt injection, handoff, aislamiento, persistencia, migraciones y tests de
seguridad. Los tests no llaman producción.

## Roadmap

- **Etapas 1–7:** arqueología, contratos, tools, memoria, Jinja/LLM, Meta oficial, goldens y
  observabilidad: implementadas y verificadas.
- **Etapa 8:** embeddings reales, pgvector, sincronización y reconfirmación: siguiente etapa activa.
- **Etapa 9:** n8n mínimo, consola Kanban autenticada, eventos firmados y despliegue público:
  pendiente.

El estado verificable está en [PIKI_STATUS.md](PIKI_STATUS.md) y la bitácora reproducible en
[PIKI_EVIDENCE.md](PIKI_EVIDENCE.md). Para operación, empezar por
[GUIA_PENDIENTES_DUENO.md](GUIA_PENDIENTES_DUENO.md).
