# Piki Local Chat Quickstart

## Arranque

Desde la raiz del repo:

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.meta-local.yml \
  -f compose.ai-local.yml \
  up -d --build --wait
```

Abrir:

```text
http://localhost:8000/console
```

Estado tecnico:

```text
http://localhost:8000/api/chat/status
http://localhost:8000/health/ready
```

## Que funciona ahora

- Chat real con Piki usando NVIDIA NIM y `z-ai/glm-5.2`.
- Historial durable en PostgreSQL y coordinacion en Redis.
- Jinja de evidencia, policy y grounding antes de mostrar una respuesta.
- Saludo, explicacion de BuenPick y pedido de atencion humana.
- Respuesta segura cuando no hay evidencia comercial confirmada.

El token de BuenPick Internal API ya esta montado localmente. La busqueda real de picks sigue
bloqueada por `PIKI_BUENPICK_ALLOW_PRODUCTION=false`, una proteccion intencional contra llamadas
productivas accidentales. Piki informa la limitacion y no inventa stock, precios ni disponibilidad.
El archivo local preparado es
`secrets/buenpick_internal_api_token.txt`; esta ruta esta ignorada por Git y su valor nunca debe
copiarse a una guia, log o captura.

## Prueba productiva local autorizada

Si vas a enviar un mensaje real desde otro numero al WhatsApp de BuenPick, usa el override explicito:

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.meta-local.yml \
  -f compose.ai-local.yml \
  -f compose.prod-local.yml \
  up -d --build --wait
```

Ese override habilita `PIKI_META_INGRESS_ENABLED`, `PIKI_CONVERSATION_WORKER_ENABLED` y el acceso
productivo de BuenPick. El worker puede responder mensajes reales y Meta puede reenviar eventos. No
lo uses para pruebas automáticas ni dejes ese perfil levantado sin supervisión.

Para que llegue un WhatsApp real, además hace falta:

1. Un HTTPS público que enrute a `http://localhost:8000` (túnel temporal o proxy de Dokploy).
2. Configurar en Meta `GET/POST <public-url>/webhooks/meta/whatsapp`.
3. Usar el verify token local y suscribir la WABA al campo `messages`.
4. Confirmar primero el challenge `GET`; recién después enviar desde el número de prueba.

Sin esos cuatro pasos el contenedor puede estar healthy, pero Meta no tiene cómo entregarle el
mensaje.

## Limites intencionales

- `PIKI_META_INGRESS_ENABLED=false`: Meta no ingresa mensajes al runtime local normal.
- `PIKI_CONVERSATION_WORKER_ENABLED=false`: el worker no envia respuestas reales a WhatsApp.
- La consola local no es el futuro Kanban autenticado de operadores.
- n8n esta healthy pero debe conservar cero workflows productivos hasta Stage 9.

No uses `docker compose down -v`: elimina estado persistente. Para diagnosticar, empezar con:

```bash
docker compose ps
docker compose logs --tail=100 piki-api piki-worker n8n
```
