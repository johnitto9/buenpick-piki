# Etapa 7 — Golden tests y observabilidad

## Objetivo

Convertir los aprendizajes del legado en especificación ejecutable.

## Golden cases

- saludo;
- búsqueda con resultados;
- búsqueda vacía;
- pick agotado antes de responder;
- active pick + foto;
- orden válida;
- orden ajena;
- timeout BuenPick;
- fallo Meta;
- handoff;
- aislamiento;
- prompt injection;
- centavos ARS;
- no inventar contenido de bolsa sorpresa.

## Observabilidad

Eventos:

```text
message_received
intent_resolved
tool_started
tool_finished
context_built
template_rendered
llm_started
llm_finished
grounding_checked
delivery_attempted
delivery_succeeded
delivery_failed
```

## Gate

- golden suite completa;
- traces correlacionadas;
- latencias medidas;
- errores diferenciados;
- sin PII innecesaria;
- ninguna afirmación “funciona” sin evidencia.
