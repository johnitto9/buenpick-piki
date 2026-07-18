# Etapa 4 — Estado, memoria y active pick

## Objetivo

Recuperar el corazón contextual de Delibot sin su state machine monolítica.

## Trabajo

- Redis;
- persistencia durable;
- active pick;
- pending action;
- locks;
- deduplicación;
- aislamiento;
- TTLs;
- reconfirmación de datos.

## Casos

```text
¿Hay una bolsa de panadería?
→ Sí, esta.
→ Mandame foto.
```

La foto corresponde al active pick.

## Gate

- conversación A no contamina B;
- active pick funciona y expira;
- locks seguros;
- dedup probado;
- stock/precio reconfirmados;
- fallback honesto ante Redis.
