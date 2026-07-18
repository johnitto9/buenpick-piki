# Mapa y plan general

## Fuentes

### Slim

```text
codigoslasts/codigo_extraido_delibotlast.txt
```

Usar para entender el flujo original y el núcleo comercial.

### Grande

```text
codigoslasts/codigo_extraido_delibotlast1.txt
```

Usar como cantera de:

- active topic;
- memoria;
- Jinja;
- PromptManager;
- AssetLoader;
- tool registry;
- pgvector;
- fotos;
- grounding;
- golden tests;
- observabilidad.

### BuenPick

```text
buenpickinternalapi/INTERNAL_API.md
```

Es el contrato real.

## Clasificación del legado

```text
MIGRATE_BEHAVIOR
REIMPLEMENT
REFERENCE_ONLY
DISCARD
```

### MIGRATE_BEHAVIOR

- active pick;
- aislamiento;
- grounding;
- foto contextual;
- handoff;
- fallos explícitos;
- golden conversations;
- separación entre evidencia y respuesta.

### REIMPLEMENT

- Jinja;
- PromptManager;
- AssetLoader;
- state;
- tools;
- pgvector;
- observabilidad;
- policies;
- sanitización.

### REFERENCE_ONLY

Documentación histórica, constitución Delify, hotfixes y routers experimentales.

### DISCARD

Scraper, Baileys, Chroma, mocks, falso delivery, credenciales, backups, caches y monolitos.

## Nueve etapas

1. Arqueología y recovery map.
2. Bootstrap y contratos.
3. Cliente BuenPick y tools.
4. Estado, memoria y active pick.
5. Jinja, LLM y grounding.
6. Meta WhatsApp oficial.
7. Golden tests y observabilidad.
8. pgvector y sincronización.
9. n8n mínimo y producción.

## Documentos de progreso

Codex debe mantener:

```text
PIKI_STATUS.md
PIKI_DECISIONS.md
PIKI_EVIDENCE.md
```

## Gate universal

Una etapa no termina hasta que:

- sus entregables existen;
- los tests pasan;
- no hay secretos;
- no hay mocks presentados como reales;
- no hay falso éxito;
- existe evidencia reproducible;
- la siguiente etapa tiene una primera tarea concreta.
