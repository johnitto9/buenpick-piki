# Etapa 5 — Jinja, LLM y grounding

## Objetivo

Implementar la separación central de Delibot de forma limpia.

## Trabajo

- system prompt corto;
- policy registry;
- ContextPacket;
- Jinja Evidence Renderer;
- templates sin datos hardcodeados;
- LLM adapter;
- fake LLM para tests;
- deterministic/Jinja/Jinja+LLM;
- grounding validator;
- sanitización;
- prompt injection defenses.

## Gate

- todo dato comercial proviene de evidencia;
- Jinja no contiene conocimiento cambiante;
- salida inventada se bloquea;
- no se filtran procesos internos;
- fallback factual;
- rutas de respuesta probadas;
- system prompt y templates tienen una única fuente.
