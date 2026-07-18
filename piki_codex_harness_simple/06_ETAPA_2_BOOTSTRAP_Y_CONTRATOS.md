# Etapa 2 — Bootstrap y contratos

## Objetivo

Crear un esqueleto mínimo, tipado, ejecutable y dockerizado desde el inicio.

## Trabajo

- estructura del repo;
- Dockerfiles productivos iniciales;
- `docker-compose.yml` local;
- healthchecks y readiness;
- configuración por entorno;
- configuración;
- modelos centrales;
- interfaces;
- lint/typecheck/tests;
- `.env.example`;
- Docker local mínimo;
- health endpoint;
- schemas de mensajes, tools, ContextPacket y delivery.

## Gate

- arranque local;
- health `200`;
- test mínimo;
- sin secretos;
- sin scaffolding muerto;
- contratos versionados;
- arquitectura alineada con los cuatro documentos fundacionales;
- todos los servicios propios arrancan en contenedores;
- no existen dependencias de rutas locales de Windows;
- los contenedores no contienen secretos.
