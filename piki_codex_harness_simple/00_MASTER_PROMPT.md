# Piki — Prompt maestro para Codex GPT-5.6

Trabajá como arquitecto e ingeniero principal dentro del repositorio actual.

El proyecto se llama **Piki** y será el asistente oficial de BuenPick, un marketplace de rescate de alimentos.

## Fuentes disponibles

En la raíz del proyecto existen:

```text
codigoslasts/codigo_extraido_delibotlast.txt
codigoslasts/codigo_extraido_delibotlast1.txt
buenpickinternalapi/INTERNAL_API.md
```

- El archivo slim muestra el corazón original de Delibot.
- El archivo grande contiene comportamiento avanzado, tests, prompts, templates, memoria, pgvector, tools, observabilidad e historia técnica.
- `INTERNAL_API.md` documenta la API real y productiva de BuenPick.

## Lectura obligatoria

Antes de implementar, leé en orden:

```text
01_INTRODUCCION_Y_PRINCIPIOS.md
02_ARQUITECTURA_TECNICA.md
03_MAPA_Y_PLAN_GENERAL.md
04_CONCILIACION_DELIBOT_BUENPICK.md
```

Después ejecutá las etapas en orden, de la 1 a la 9.

## Loop obligatorio

En la raíz creá y mantené:

```text
PIKI_STATUS.md
PIKI_DECISIONS.md
PIKI_EVIDENCE.md
```

En cada iteración:

1. leé los cuatro documentos fundacionales;
2. leé la etapa activa;
3. leé `PIKI_STATUS.md`;
4. elegí una sola tarea verificable;
5. inspeccioná antes de editar;
6. implementá el cambio mínimo;
7. ejecutá tests y validaciones;
8. revisá arquitectura, exactitud, seguridad y fallos;
9. registrá evidencia;
10. actualizá estado y siguiente tarea;
11. avanzá únicamente cuando el gate de la etapa esté demostrado.

No pidas confirmación por decisiones menores. Documentá la decisión y seguí.

## Decisiones no negociables

- Se elimina completamente el scraper.
- BuenPick Internal API es la única fuente de verdad operacional.
- Se elimina Baileys y cualquier integración no oficial de WhatsApp.
- Se utiliza **Meta WhatsApp Cloud API oficial**.
- No se accede directamente a la base de datos de BuenPick.
- No se duplican reglas de stock, precio, disponibilidad ni propiedad de órdenes.
- PostgreSQL + pgvector es el único motor vectorial.
- Redis se usa para estado efímero y coordinación.
- Jinja estructura evidencia; no funciona como base de conocimiento.
- El LLM redacta y conversa, pero no decide hechos comerciales.
- n8n tiene una capa mínima y operativa.
- No se copian god objects ni módulos históricos enteros.
- No se reutilizan secretos encontrados en el legado.
- No se reporta delivery exitoso si Meta lo rechazó.
- Checkout interno de Piki no está habilitado actualmente.
- Los tests no deben llamar a producción.

## Principio central heredado de Delibot

> Primero construir una representación confiable de la realidad. Después permitir que el modelo la transforme en lenguaje.

El patrón que debe recuperarse de manera limpia es:

```text
contexto + memoria + tools
→ ContextPacket tipado
→ template Jinja inteligente
→ system prompt + directiva + conversación
→ LLM cuando corresponde
→ grounding validator
→ delivery oficial por Meta
```

## Inicio

Comenzá con:

```text
05_ETAPA_1_ARQUEOLOGIA_Y_RECOVERY_MAP.md
```

No implementes runtime antes de completar su gate.

## Requisito transversal de infraestructura

Todo componente que forme parte del runtime debe quedar preparado para ejecución reproducible mediante Docker.

Como mínimo:

- `Dockerfile` por aplicación o servicio propio;
- `docker-compose.yml` para desarrollo local;
- servicios separados para API, worker, PostgreSQL + pgvector, Redis y n8n;
- configuración exclusivamente por variables de entorno;
- healthchecks y readiness checks;
- migraciones reproducibles;
- almacenamiento persistente explícito;
- logs a stdout/stderr en formato estructurado;
- usuario no root cuando sea viable;
- imágenes pequeñas y builds multistage;
- graceful shutdown;
- límites de recursos documentados;
- sin secretos embebidos;
- diferencias entre desarrollo y producción claramente separadas;
- despliegue compatible con Docker/Dokploy/Swarm o una plataforma equivalente.

`Prod ready` no significa desplegar prematuramente. Significa que ninguna decisión temprana debe impedir un despliegue seguro, observable y reversible.
