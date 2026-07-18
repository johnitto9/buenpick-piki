# Delibot Internal API

API interna para que Delibot consulte datos reales de BuenPick sin scraping y sin acceso directo a PostgreSQL.

Base productiva:

```text
https://api.buenpick.com.ar/internal/v1
```

## Estado

Deployado en producción desde commit `15e5976`.

Servicios actualizados en VPS:

- `buenpick-bpapi-nbbuhl`
- `buenpick-bpworker-i6iwnh`

El token productivo está configurado en Dokploy para `bp-api` y aplicado al servicio Swarm. También quedó guardado en el VPS, con permisos root, en:

```text
/root/buenpick-delibot-internal-token.txt
```

No imprimir este token en logs, tickets, capturas ni chats.

## Autenticación

Todas las rutas requieren Bearer token:

```http
Authorization: Bearer <DELIBOT_INTERNAL_API_TOKEN>
```

Variable de entorno:

```text
DELIBOT_INTERNAL_API_TOKEN=
```

Generación sugerida:

```bash
openssl rand -base64 32
```

Si el token falta o es incorrecto, la API responde `401`. Si el backend no tiene `DELIBOT_INTERNAL_API_TOKEN` configurado, responde `503`.

## Reglas de Disponibilidad

Un pick aparece como disponible solo si cumple todo esto:

- `Pick.status = active`
- `Pick.pickupEnd > now`
- `Pick.quantityAvailable > 0`
- `Store.status = active`

No se devuelven picks agotados, vencidos, pausados, cancelados, en draft ni de comercios no activos.

Los precios están en centavos de ARS, igual que en el resto del backend BuenPick.

## Quick Start

```bash
TOKEN="..."
BASE_URL="https://api.buenpick.com.ar/internal/v1"

curl -s \
  -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/picks/search?q=bolsa"
```

Resultado vacío válido:

```json
{
  "items": [],
  "total": 0
}
```

Delibot debe tratar `items: []` como "no hay picks disponibles para esa búsqueda", no como error.

## Endpoints

### Buscar Picks Disponibles

```http
GET /internal/v1/picks/search?q={query}&commerce_id={optional}
```

Parámetros:

- `q`: texto opcional. Busca por título del pick.
- `commerce_id`: opcional. Limita la búsqueda a un comercio.

Límite actual: 20 resultados.

Ejemplo:

```bash
curl -s \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.buenpick.com.ar/internal/v1/picks/search?q=pan"
```

Respuesta:

```json
{
  "items": [
    {
      "id": "pick_id",
      "title": "Bolsa sorpresa",
      "description": "Mix del dia",
      "price": 250000,
      "original_price": 600000,
      "available_quantity": 2,
      "status": "AVAILABLE",
      "image_url": "https://...",
      "commerce": {
        "id": "commerce_id",
        "name": "Panaderia Centro"
      }
    }
  ],
  "total": 1
}
```

### Obtener Detalle de Pick

```http
GET /internal/v1/picks/{pick_id}
```

Solo devuelve picks comprables actualmente. Si el pick existe pero está agotado, vencido o no publicable, responde `404`.

Ejemplo:

```bash
curl -s \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.buenpick.com.ar/internal/v1/picks/pick_id"
```

Respuesta:

```json
{
  "id": "pick_id",
  "title": "Bolsa sorpresa",
  "description": "Mix del dia",
  "price": 250000,
  "original_price": 600000,
  "available_quantity": 2,
  "status": "AVAILABLE",
  "image_url": "https://...",
  "images": ["https://..."],
  "category": "panaderia",
  "pickup": {
    "starts_at": "2026-07-16T18:00:00.000Z",
    "ends_at": "2026-07-16T21:00:00.000Z"
  },
  "conditions": {
    "quantity_available": 2,
    "approx_weight_grams": 800,
    "fulfillment": {
      "pickup": true,
      "delivery_enabled": false,
      "delivery_eta_min_minutes": null,
      "delivery_eta_max_minutes": null
    }
  },
  "commerce": {
    "id": "commerce_id",
    "name": "Panaderia Centro",
    "description": "Panes y facturas",
    "address": "Alsina 123",
    "city": "Bahia Blanca",
    "zone": "centro",
    "status": "active",
    "opening_hours": null
  },
  "public_url": "https://buenpick.com.ar/picks/pick_id"
}
```

### Obtener Comercio

```http
GET /internal/v1/commerces/{commerce_id}
```

Devuelve información útil para atención al cliente. No expone owner, tokens, datos financieros ni configuración administrativa privada.

Ejemplo:

```bash
curl -s \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.buenpick.com.ar/internal/v1/commerces/commerce_id"
```

Respuesta:

```json
{
  "id": "commerce_id",
  "name": "Panaderia Centro",
  "slug": "panaderia-centro",
  "description": "Panes y facturas",
  "address": "Alsina 123",
  "city": "Bahia Blanca",
  "zone": "centro",
  "phone": "2914555555",
  "status": "active",
  "opening_hours": null,
  "pickup_instructions": null,
  "delivery": {
    "enabled": false,
    "fee_cents": null,
    "eta_min_minutes": null,
    "eta_max_minutes": null
  },
  "accepts_cash_on_pickup": true,
  "logo_url": "https://...",
  "cover_url": null
}
```

### Consultar Orden

```http
GET /internal/v1/orders/{order_id}?customer_phone={telefono}
GET /internal/v1/orders/{order_id}?customer_reference={referencia}
```

Requiere validar pertenencia de la orden. No alcanza con saber el `order_id`.

Validaciones aceptadas:

- `customer_phone`: compara contra el teléfono snapshot de la orden y contra el teléfono del usuario, normalizando dígitos.
- `customer_reference`: compara contra `userId` o email del usuario BuenPick.

Si la validación no coincide, responde `401`.

Ejemplo:

```bash
curl -s \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.buenpick.com.ar/internal/v1/orders/order_id?customer_phone=2914555555"
```

Respuesta:

```json
{
  "id": "order_id",
  "status": "paid",
  "commerce": {
    "id": "commerce_id",
    "name": "Panaderia Centro",
    "address": "Alsina 123",
    "opening_hours": null
  },
  "picks": [
    {
      "pick_id": "pick_id",
      "title": "Bolsa sorpresa",
      "quantity": 1,
      "unit_price": 250000,
      "line_total": 250000,
      "image_url": "https://..."
    }
  ],
  "total": 250000,
  "fulfillment": {
    "type": "pickup",
    "delivery_address": null,
    "delivery_notes": null,
    "pickup_code": "ABC123"
  },
  "pickup": {
    "instructions": null,
    "store_address": "Alsina 123"
  },
  "dates": {
    "created_at": "2026-07-16T10:00:00.000Z",
    "expires_at": null,
    "confirmed_at": "2026-07-16T10:02:00.000Z",
    "paid_at": "2026-07-16T10:02:00.000Z",
    "preparing_at": null,
    "ready_at": null,
    "out_for_delivery_at": null,
    "delivered_at": null,
    "picked_up_at": null
  }
}
```

### Checkout Sessions

```http
POST /internal/v1/checkout-sessions
```

No está habilitado en esta versión.

Motivo: BuenPick ya tiene `checkoutOrder`, que protege stock con transacción y `SELECT ... FOR UPDATE`, pero requiere un `userId` real, datos de contacto y luego el flujo de pago correspondiente. El contrato mínimo de Delibot no alcanza para crear checkout sin inventar identidad o duplicar lógica.

Respuesta actual:

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "Checkout interno para Delibot no está habilitado: requiere identidad de usuario y flujo de pago existente."
  }
}
```

## Errores

- `400 BAD_REQUEST`: query/body inválido o endpoint no habilitado.
- `401 UNAUTHORIZED`: falta token, token inválido, o la orden no pertenece al cliente consultado.
- `404 NOT_FOUND`: recurso inexistente. En detalle de pick también significa "no disponible actualmente".
- `429 TOO_MANY_REQUESTS`: límite de requests.
- `503 SERVICE_UNAVAILABLE`: falta `DELIBOT_INTERNAL_API_TOKEN` en el backend.
- `500 INTERNAL_ERROR`: error inesperado.

## Rate Limit

La API interna usa el rate limit global del backend y además un límite por ruta de:

```text
120 requests / minuto
```

## Limitaciones Actuales

- No hay campo persistido de instrucciones de retiro por comercio; se devuelve `pickup_instructions: null`.
- La búsqueda es textual simple sobre título del pick.
- No usa embeddings, pgvector ni scraping.
- El detalle de pick solo muestra picks disponibles. Para atención sobre picks históricos, consultar la orden.
- Checkout para Delibot queda pendiente hasta definir identidad de usuario y URL de pago sin duplicar `checkoutOrder` ni `payments/create-preference`.

## Tests Locales

Tests específicos:

```bash
pnpm --filter @buen-pick/api test -- src/routes/__tests__/internal-delibot.test.ts
```

Typecheck:

```bash
pnpm --filter @buen-pick/api check-types
```

Suite API completa:

```bash
pnpm --filter @buen-pick/api test
```

## Smoke Productivo

Sin imprimir el token:

```bash
token=$(ssh -i ~/.ssh/buenpick_vps root@76.13.230.238 \
  'cat /root/buenpick-delibot-internal-token.txt')

curl -s -o /dev/null -w "%{http_code}\n" \
  "https://api.buenpick.com.ar/health"

curl -s -o /dev/null -w "%{http_code}\n" \
  "https://api.buenpick.com.ar/internal/v1/picks/search?q=smoke"

curl -s \
  -H "Authorization: Bearer $token" \
  "https://api.buenpick.com.ar/internal/v1/picks/search?q=smoke"
```

Resultados esperados:

- Health: `200`
- Sin token: `401`
- Con token: `200`
- Si no hay resultados: `{"items":[],"total":0}`

## Archivos Relevantes

- `apps/api/src/routes/internal-delibot.ts`
- `apps/api/src/routes/__tests__/internal-delibot.test.ts`
- `apps/api/src/config/env.ts`
- `apps/api/src/server.ts`
- `docs/DELIBOT_INTERNAL_API.md`
