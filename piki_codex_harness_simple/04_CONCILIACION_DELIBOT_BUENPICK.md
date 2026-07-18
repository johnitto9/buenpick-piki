# Conciliación Delibot ↔ BuenPick ↔ Piki

Este documento define cómo transformar el ADN de Delibot en una arquitectura propia de BuenPick.

## BuenPick conserva

- stock;
- precio;
- disponibilidad;
- comercios;
- retiro;
- imágenes;
- órdenes;
- propiedad;
- URL pública;
- checkout real.

BuenPick no delega estas decisiones en Piki.

## Piki aporta

- conversación;
- interpretación;
- memoria;
- active pick;
- tools;
- Jinja;
- personalidad;
- grounding;
- WhatsApp oficial;
- handoff;
- trazabilidad.

## Delibot aporta como legado

### Corazón

```text
mensaje
→ contexto
→ tools
→ borrador factual
→ fusión conversacional
→ entrega
```

### Patrones valiosos

- active topic;
- memoria por conversación;
- tool registry;
- Jinja como etapa intermedia;
- system prompt separado;
- resultados de herramientas incorporados a la fusión;
- fotos con contexto;
- golden tests;
- observabilidad por etapas.

## Transformaciones

### Delify → BuenPick

Eliminar:

- mayorista/minorista;
- catálogo estable;
- productos internacionales;
- reposición;
- scraping;
- lógica de stock local.

Agregar:

- picks oportunísticos;
- bolsas sorpresa;
- ventana de retiro;
- comercio;
- disponibilidad temporal;
- compra mediante `public_url`;
- validación de órdenes.

### WhatsApp viejo → Meta oficial

Eliminar:

- Baileys;
- bridge custom;
- resolución de imágenes por archivos locales;
- payload custom `{phone, message}`;
- ausencia de firmas y estados.

Agregar:

- webhook oficial;
- verify token;
- app secret;
- firma;
- `wamid`;
- status callbacks;
- templates aprobados;
- media oficial;
- idempotencia.

### Jinja viejo → Evidence Renderer

Eliminar:

- ejemplos hardcodeados;
- múltiples copias de playbooks;
- lógica comercial en templates;
- templates que hablan directamente.

Conservar:

- estructura factual;
- variables tipadas;
- template por policy;
- separación entre datos y voz.

## Flujo conciliado

```text
mensaje Meta
→ normalización
→ estado
→ policy
→ tools BuenPick
→ ContextPacket
→ Jinja Evidence
→ LLM opcional
→ grounding
→ Meta Delivery
```

## Regla final

BuenPick es la realidad.  
Piki es la interfaz inteligente.  
Delibot es la fuente de aprendizaje, no la base de código.
