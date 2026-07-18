# Meta Production Handoff

Estado verificado el 2026-07-18. Este documento no contiene credenciales.

## Estado actual

| Configuracion | Estado |
|---|---|
| App ID | Presente y confirmado por Graph API |
| App Secret | Presente en archivo local ignorado y validado con `appsecret_proof` |
| System User long-lived access token | Presente en archivo local ignorado |
| WABA ID productivo | Presente y confirmado por Graph API |
| Phone Number ID productivo | Presente y confirmado por Graph API |
| Graph API | `v25.0` |
| Webhook verify token | Generado y rotado en archivo local ignorado |
| `whatsapp_business_management` | Concedido |
| `whatsapp_business_messaging` | Concedido |
| `PIKI_META_INGRESS_ENABLED` | `false` |
| `PIKI_CONVERSATION_WORKER_ENABLED` | `false` |
| Delivery endpoint | Implementado y sin mensajes reales enviados |
| Processing outbox | Implementado y probado con adaptador local falso |

Las consultas de validacion fueron solamente `GET`, incluido `appsecret_proof`. No se enviaron
mensajes, no se modificaron activos de Meta y no se configuro el webhook.

Los callbacks se registran primero en PostgreSQL. Piki emite `delivery_succeeded` unicamente despues
de confirmar durablemente `delivered`, y `delivery_failed` despues de confirmar `failed`. Los estados
`accepted`, `sent` y `read`, los replays y las regresiones no generan un falso evento de entrega.

Los mensajes entrantes quedan en un outbox PostgreSQL y el worker los reclama de forma idempotente.
El flujo completo de composicion fue probado con GLM-5.2 y un adaptador de entrega falso: no hubo un
`POST /messages` real. En local, ingress y procesamiento productivo siguen apagados.

## Configuracion local

`.env` contiene solamente IDs y opciones no secretas. El App Secret, access token y webhook verify
token se montan como archivos con el override
[compose.meta-local.yml](../../compose.meta-local.yml).

La prueba local de `POST /webhooks/meta/whatsapp` con firma real y payload sintetico confirmo un
primer ingreso y un replay duplicado contra PostgreSQL y Redis. La fixture se elimino al terminar.

Validacion segura, sin iniciar ingress ni enviar mensajes:

```bash
docker compose -f docker-compose.yml -f compose.meta-local.yml config --quiet
```

No activar `PIKI_META_INGRESS_ENABLED` hasta desplegar HTTPS y completar las pruebas del callback
publico. No colocar valores reales en `.env.example`.

## Dokploy

1. Publicar una imagen inmutable de Piki y ejecutar migraciones hasta
   `0004_message_processing_outbox` antes de levantar API y worker.
2. Crear los secretos de plataforma `meta_app_secret`, `meta_access_token` y
   `meta_webhook_verify_token` usando los valores locales ya preparados. Crear tambien
   `llm_api_key` y `buenpick_internal_api_token`; el token de BuenPick todavia no esta disponible en
   este entorno local.
3. Configurar las variables no secretas:

```text
PIKI_META_APP_ID=<App ID confirmado>
PIKI_META_WABA_ID=<WABA productivo confirmado>
PIKI_META_PHONE_NUMBER_ID=<Phone Number ID productivo confirmado>
PIKI_META_GRAPH_API_VERSION=v25.0
PIKI_META_GRAPH_BASE_URL=https://graph.facebook.com
PIKI_META_DELIVERY_TIMEOUT_SECONDS=10
PIKI_META_INGRESS_ENABLED=false
PIKI_CONVERSATION_ENABLED=true
PIKI_CONVERSATION_WORKER_ENABLED=false
PIKI_LLM_PROVIDER=nvidia_nim
PIKI_LLM_MODEL=z-ai/glm-5.2
PIKI_LLM_BASE_URL=https://integrate.api.nvidia.com/v1
PIKI_BUENPICK_INTERNAL_API_BASE_URL=https://api.buenpick.com.ar/internal/v1
```

4. Montar los cinco secretos en las rutas declaradas por `deploy/stack.yml`.
5. Exponer solamente `piki-api:8000` mediante HTTPS en `piki-api.buenpick.com.ar`; PostgreSQL,
   Redis y worker permanecen internos.
6. Comprobar `GET /health/ready` y revisar logs sanitizados antes de continuar.

## Cloudflare

1. Crear el registro DNS de `piki-api.buenpick.com.ar` apuntando al destino que entregue Dokploy.
2. Usar TLS valido de extremo a extremo y modo `Full (strict)` si Cloudflare actua como proxy.
3. No cachear `/webhooks/meta/whatsapp`.
4. Permitir `GET` y `POST` en esa ruta sin challenge interactivo ni transformacion del body.
5. Conservar `X-Hub-Signature-256`; Piki valida la firma sobre los bytes exactos recibidos.

No cambiar DNS ni reglas hasta conocer el destino publico definitivo de Dokploy.

## Meta

Estos pasos son posteriores; no ejecutarlos todavia:

1. Desplegar Piki con App Secret y verify token montados, manteniendo ingress en `false`.
2. Confirmar que `/health/ready` responde correctamente por HTTPS.
3. Configurar como callback:

```text
https://piki-api.buenpick.com.ar/webhooks/meta/whatsapp
```

4. Usar el verify token ya generado y suscribir el campo `messages`.
5. Confirmar challenge correcto, rechazo de token incorrecto y rechazo de firma invalida.
6. Recién entonces cambiar `PIKI_META_INGRESS_ENABLED=true`; mantener el worker apagado y comprobar
   que el inbound queda persistido.
7. Activar `PIKI_CONVERSATION_WORKER_ENABLED=true` solo con LLM, BuenPick y Meta delivery resueltos.
8. Probar entrada, imagen y callbacks `sent`, `delivered`, `read` y `failed`.
9. No enviar una prueba real hasta definir `PIKI_META_TEST_RECIPIENT` y tener autorizacion expresa.
10. No publicar la app hasta completar el smoke real y demostrar que `accepted` no se reporta como
   `delivered`.

n8n esta healthy, con administrador creado y cero workflows productivos. No participa en este flujo;
los workflows siguen diferidos hasta que Piki publique los contratos firmados e idempotentes de
Stage 9.
