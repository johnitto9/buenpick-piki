# Etapa 6 — Meta WhatsApp oficial

## Objetivo

Reemplazar completamente la integración histórica por Meta WhatsApp Cloud API.

## Trabajo

- verify challenge;
- signature validation;
- payload normalization;
- dedup por `wamid`;
- texto;
- imágenes;
- interactive cuando sea útil;
- outbound delivery;
- status callbacks;
- template messages;
- ventana de atención;
- idempotencia;
- retries;
- fixtures anonimizados.

## Prohibido

- Baileys;
- bridge custom;
- payload legado;
- archivos locales resueltos por nombre;
- falso éxito;
- acoplar el core a Meta.

## Gate

- firma inválida rechazada;
- duplicados descartados;
- mensajes normalizados;
- imagen real enviada por adapter;
- estados accepted/delivered/read/failed registrados;
- fallo visible;
- core independiente del canal.
