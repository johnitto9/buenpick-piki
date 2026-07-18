# Arquitectura técnica

## Flujo principal

```text
Meta WhatsApp Cloud API
        ↓
Webhook oficial
        ↓
Validación de firma + deduplicación
        ↓
Normalización de mensaje
        ↓
Conversation Orchestrator
   ├── Redis: estado efímero
   ├── PostgreSQL: persistencia
   ├── Tools tipadas
   │     └── BuenPick Internal API
   ├── pgvector
   ├── Jinja Evidence Renderer
   ├── LLM Composer
   └── Grounding Validator
        ↓
Delivery Service
        ↓
Meta WhatsApp Cloud API
```

## Componentes

### BuenPick Client

Responsable de:

- Bearer token;
- timeouts;
- retries;
- mapping de errores;
- precios en centavos;
- búsqueda;
- detalle;
- comercio;
- órdenes;
- validación de pertenencia.

No contiene reglas comerciales duplicadas.

### Tool layer

Tools iniciales:

```text
search_available_picks
get_available_pick
get_commerce
get_customer_order
send_pick_image
request_human_handoff
```

Contrato común:

```json
{
  "success": true,
  "data": {},
  "error_code": null,
  "user_safe_message": null,
  "latency_ms": 0,
  "trace_id": "..."
}
```

Las tools devuelven datos. No envían mensajes por sí mismas.

### Estado

Redis:

- active pick;
- pending action;
- deduplicación;
- locks;
- estado reciente.

PostgreSQL:

- conversaciones;
- mensajes;
- ejecuciones de tools;
- delivery attempts;
- handoffs;
- traces;
- evaluaciones.

### pgvector

Usos separados:

- catálogo semántico;
- conocimiento estable;
- memoria de usuario.

Un resultado vectorial es un candidato. Antes de informar stock o precio se reconfirma con BuenPick.

### Prompt pipeline

```text
Policy
→ Tools
→ ContextPacket
→ Jinja
→ LLM opcional
→ Grounding
```

Modos:

- determinista;
- Jinja puro;
- Jinja + LLM;
- LLM sin datos comerciales.

Nunca LLM puro para stock, precio, orden, propiedad, URL o código de retiro.

### Meta WhatsApp oficial

Separar:

```text
verification
signature validation
payload normalization
wamid deduplication
outbound delivery
status callbacks
template messages
media messages
```

El core no consume payloads crudos de Meta.

Estados reales:

```text
accepted
sent
delivered
read
failed
```

Nunca simular éxito.

### n8n

Solo:

1. handoff humano;
2. avisos por estado de orden;
3. resumen operativo diario.

n8n no razona, no accede a DB y no habla directamente con Meta.

## Infraestructura dockerizada

La arquitectura se diseña desde el inicio para correr completamente en contenedores:

```text
piki-api
piki-worker
postgres-pgvector
redis
n8n
```

Requisitos:

- un `Dockerfile` multistage por aplicación propia;
- `docker-compose.yml` local;
- compose o stack de producción separado;
- healthchecks;
- readiness;
- migraciones ejecutables;
- volúmenes persistentes;
- redes internas;
- servicios sin puertos públicos innecesarios;
- variables de entorno;
- logs estructurados;
- graceful shutdown;
- política de restart;
- backups y restore documentados;
- compatibilidad con Dokploy/Swarm.

El core no debe depender de rutas locales de Windows ni de procesos ejecutados fuera del contenedor.
