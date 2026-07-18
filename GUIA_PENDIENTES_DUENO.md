# Guia facil: que funciona y que te queda hacer

## Probar Piki ahora

El chat local ya responde con NVIDIA NIM y GLM-5.2. Desde la raiz del repo:

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.meta-local.yml \
  -f compose.ai-local.yml \
  up -d --build --wait
```

Abrir `http://localhost:8000/console`.

Funcionan el chat, historial PostgreSQL, Redis, Jinja, grounding y pedidos de atencion humana. La
busqueda comercial no esta habilitada todavia porque el guard de produccion sigue apagado; Piki
responde sin inventar stock, precio ni disponibilidad. El token ya esta montado de forma segura.
Detalle: `docs/operations/LOCAL_CHAT_QUICKSTART.md`.

## Lo que tenes que hacer vos

1. Conseguir el token productivo de BuenPick Internal API. Ya fue localizado desde
   `/home/juan/.secrets/buenpick/delibot_internal_api_token.txt` y guardado localmente en
   `secrets/buenpick_internal_api_token.txt` (ignorado por Git). La fuente canonica protegida sigue
   siendo `/home/juan/.secrets/buenpick/delibot_internal_api_token.txt`; el archivo del repo existe
   solo porque Docker Desktop no monta correctamente un symlink WSL desde `/mnt/c`. El contrato indica
   que el token existente
   se administra en Dokploy para el servicio `bp-api` y no debe regenerarse sin coordinar la rotacion
   del backend.
2. Para probar ahora desde local con tu autorización, levantar el perfil `compose.prod-local.yml`
   explicado en `docs/operations/LOCAL_CHAT_QUICKSTART.md`; después apagarlo al terminar.
3. Elegir el destino de Dokploy y apuntar `piki-api.buenpick.com.ar` con HTTPS.
3. Crear en Dokploy los secretos indicados en `docs/operations/META_PRODUCTION_HANDOFF.md`.
4. Configurar el callback de Meta solo despues del deploy y del healthcheck publico.
5. Autorizar expresamente un destinatario de prueba antes del primer WhatsApp real.
6. Elegir un dominio privado y protegido para el editor de n8n.

Los IDs, token de Meta, App Secret, verify token y API key de NVIDIA ya estan preparados localmente
sin copiarlos a documentacion. Meta ingress y el worker de respuestas siguen apagados, por lo que no
se envio ningun mensaje real.

### Como obtener/configurar el token de BuenPick

La fuente correcta es el secreto del servicio `bp-api` en Dokploy (o el responsable del backend
BuenPick). El contrato historico tambien documenta una copia protegida en el VPS, pero no hay que
leerla ni pegarla en el repo, tickets o chats. No generes otro token si el backend ya usa uno: una
rotacion requiere actualizar el backend y Piki coordinadamente.

Cuando tengas el valor, guardalo en un secreto de Dokploy llamado `buenpick_internal_api_token` y
montalo en Piki como `/run/secrets/buenpick_internal_api_token`. En local, usa un archivo ignorado y
configura `PIKI_BUENPICK_INTERNAL_API_TOKEN_FILE` apuntando a ese archivo; nunca lo imprimas. Piki
enviara `Authorization: Bearer ...` a:

```text
https://api.buenpick.com.ar/internal/v1
```

El token requiere permisos sobre esa API interna. Un `401` significa token ausente/incorrecto y un
`503` indica que el backend no tiene configurado su secreto. El endpoint de prueba de lectura es
`GET /picks/search`; una respuesta `items: []` es valida y significa que no hay picks confirmados.

## n8n

n8n esta healthy en `http://localhost:5678`, tiene administrador y cero workflows productivos. No
tenes que crear ninguno todavia. En Stage 9 Piki entregara los contratos y solamente se armaran:

1. Aviso interno de pedido de atencion humana.
2. Aviso operativo de cambio de orden.
3. Resumen diario.

n8n no responde chats, no llama a Meta, no consulta bases de datos y no decide stock ni precios.

No reemplaces `.env.example` por `.env`: la primera es plantilla y la segunda es tu configuracion
local ignorada. Cambiar secretos en `.env` no modifica volumenes ya inicializados. Nunca regeneres
`N8N_ENCRYPTION_KEY` cuando existan credenciales y no uses `docker compose down -v`. Ante problemas,
primero ejecuta `docker compose logs --tail=100 n8n`.

Guia corta: `docs/operations/N8N_OWNER_QUICKSTART.md`.

## Orden de activacion de WhatsApp

1. Desplegar imagen inmutable y migrar hasta `0004_message_processing_outbox`.
2. Mantener `PIKI_META_INGRESS_ENABLED=false` y
   `PIKI_CONVERSATION_WORKER_ENABLED=false`.
3. Verificar `https://piki-api.buenpick.com.ar/health/ready`.
4. Configurar en Meta el callback
   `https://piki-api.buenpick.com.ar/webhooks/meta/whatsapp` y el campo `messages`.
5. Activar ingress, confirmar que el inbound se persiste y recien despues activar el worker.
6. Probar `accepted`, `sent`, `delivered`, `read` y `failed` por separado.

No considerar `accepted` como entregado: el exito real llega con el callback `delivered`.

## Todavia pendiente en el repo

- Etapa 8: pgvector y sincronizacion con reconfirmacion obligatoria en BuenPick.
- Etapa 9: Kanban autenticado de operadores, eventos firmados de n8n y despliegue productivo.
- Prueba final autorizada con WhatsApp real y BuenPick productivo.

Piki no esta terminado para produccion, pero el vertical conversacional local ya es utilizable y esta
probado. Estado tecnico: `PIKI_STATUS.md`.
