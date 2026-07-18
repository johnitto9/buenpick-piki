# Introducción y principios

## Qué es Piki

Piki es el asistente oficial de BuenPick por WhatsApp.

BuenPick no es un ecommerce tradicional. Es un marketplace de rescate de alimentos:

- el catálogo cambia constantemente;
- los picks tienen stock corto;
- existen ventanas de retiro;
- los productos pueden agotarse rápido;
- un pick puede no volver a publicarse;
- cada comercio conserva su propia información y condiciones.

Piki debe ayudar a:

- descubrir picks disponibles;
- explicar la propuesta de BuenPick;
- mostrar detalles reales;
- informar comercio y retiro;
- enviar imágenes reales;
- mantener el pick activo en conversación;
- consultar órdenes validando pertenencia;
- dirigir a la URL pública de compra;
- solicitar atención humana.

## El corazón que se recupera de Delibot

Delibot descubrió una separación valiosa:

```text
verdad
→ estructura
→ personalidad
→ lenguaje
```

En su versión más madura esto aparecía como:

```text
E1: contexto, memoria, RAG y herramientas
E2: borrador factual con Jinja
E3: fusión con system prompt, conversación y directiva
E4: entrega y observabilidad
```

Piki conserva esa idea, pero elimina la maquinaria histórica innecesaria.

## Jinja como template inteligente

Jinja no es una respuesta fija ni una base de conocimiento.

Su función es transformar datos tipados en un paquete de evidencia claro para el modelo:

```text
TAREA
CONSULTA
DATOS CONFIRMADOS
DATOS AUSENTES
REGLAS
ACCIONES REALIZADAS
```

Ejemplo conceptual:

```text
TAREA:
Responder sobre picks disponibles.

CONSULTA:
“¿Hay algo dulce para retirar hoy?”

DATOS CONFIRMADOS:
- Bolsa sorpresa de pastelería
- Precio: $3.500
- Stock: 2
- Retiro: 18:00–21:00
- Comercio: Panadería Centro

REGLAS:
- No inventar el contenido exacto.
- No mencionar productos fuera de la evidencia.
- Ofrecer la URL pública.
```

Después el LLM lo convierte en lenguaje natural usando la personalidad de Piki.

## Qué no se recupera

- scraper;
- Baileys;
- puente custom de WhatsApp;
- ChromaDB;
- embeddings simulados;
- tools mock;
- falso éxito de delivery;
- versiones V4–V17 dentro del runtime;
- prompts y playbooks duplicados;
- state machine monolítica;
- AI service monolítico;
- credenciales;
- caches, backups y carpetas fallidas.

## Regla de exactitud

Todo dato comercial debe provenir de:

```text
BuenPick Internal API
```

pgvector, memoria y LLM solo ayudan a comprender, buscar, ordenar o redactar.
