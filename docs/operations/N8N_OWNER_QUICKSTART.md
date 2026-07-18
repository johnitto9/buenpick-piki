# n8n Owner Quickstart

Esta guia es lo minimo que tenes que hacer de tu lado para dejar n8n listo sin romper la arquitectura de Piki.

## Respuesta corta

No reemplaces `.env.example` por `.env`.

- `.env.example`: plantilla del repo, sin secretos reales. Queda como referencia.
- `.env`: tu archivo local real. Docker Compose lo lee automaticamente. Esta ignorado por git.

Si ya existe `.env`, editalo. Si no existe, crealo copiando `.env.example`.

## Que valores tocar en `.env`

Para n8n local, estos son los importantes:

```text
N8N_DB_PASSWORD=<una clave local para la base n8n>
N8N_ENCRYPTION_KEY=<clave larga generada una sola vez>
N8N_PORT=5678
N8N_HOST=localhost
N8N_PROTOCOL=http
N8N_EDITOR_BASE_URL=http://localhost:5678
N8N_WEBHOOK_URL=http://localhost:5678
GENERIC_TIMEZONE=America/Argentina/Buenos_Aires
```

Para generar `N8N_ENCRYPTION_KEY`:

```bash
openssl rand -hex 32
```

Guardala. Si la cambias despues, n8n puede dejar de poder leer credenciales guardadas.

## Importante: `.env` no reemplaza el estado persistente

Cambiar un secreto en `.env` solo cambia lo que recibe el contenedor al arrancar. No reescribe
automaticamente datos que ya fueron inicializados en los volumenes:

- PostgreSQL puede conservar el password anterior del rol `n8n`.
- El volumen `piki_n8n_data` puede conservar la encryption key con la que n8n fue inicializado.

Una vez que n8n tenga credenciales guardadas, **nunca regeneres `N8N_ENCRYPTION_KEY`**: conserva y
respalda la misma clave. Tampoco uses `docker compose down -v`; elimina volumenes y puede destruir
la configuracion, workflows, credenciales cifradas y bases locales.

Si un entorno ya inicializado deja de arrancar despues de editar `.env`, diagnostica primero sin
borrar nada:

```bash
docker compose ps n8n
docker compose logs --tail=100 n8n
```

Busca primero un mismatch de encryption key o autenticacion PostgreSQL. Corregir esos estados es una
operacion puntual: no borres volumenes ni regeneres claves como solucion general.

## Que tenes que hacer ahora en n8n local

1. Verificar que `.env` tenga `N8N_DB_PASSWORD` y la `N8N_ENCRYPTION_KEY` ya inicializada.
2. Levantar o verificar el stack:

```bash
docker compose up -d --wait n8n
```

3. Entrar a:

```text
http://localhost:5678
```

4. El usuario administrador local ya esta creado.
5. Mantener cero workflows productivos por ahora.

## Que NO tenes que hacer todavia

- No conectar n8n a Meta WhatsApp.
- No conectar n8n a la base de datos de Piki.
- No conectar n8n a la API interna de BuenPick.
- No hacer que n8n responda chats.
- No hacer que n8n decida stock, precio, retiro, disponibilidad u ordenes.
- No usar n8n como webhook publico de WhatsApp.

Meta tiene que llamar a Piki, no a n8n.

## Para que va a servir n8n en Piki

Cuando Stage 9 este implementada, n8n solo va a consumir eventos firmados e idempotentes publicados por Piki.

Workflows permitidos:

1. Avisar internamente cuando una conversacion pasa a `needs_human`.
2. Avisar internamente cambios operativos de orden.
3. Generar un resumen diario operativo.

n8n no va a reclamar conversaciones, mover Kanban, responder usuarios ni llamar a Meta. Eso lo hace Piki.

## Datos que necesito que definas vos

Anota estos datos para produccion, sin pegarlos en chats ni commitearlos:

```text
N8N_HOST=n8n.<tu-dominio>
N8N_ENCRYPTION_KEY=<clave definitiva respaldada>
N8N_DB_PASSWORD=<password de produccion o secret de Dokploy/Swarm>
```

Tambien defini como se va a restringir el acceso al editor de n8n en produccion:

- dominio privado;
- login fuerte;
- restriccion de red o autenticacion del proxy si Dokploy lo permite.

## Cuando Piki llegue a Stage 9

En ese momento falta que el repo entregue:

- endpoints/eventos firmados para n8n;
- payloads idempotentes;
- workflows exportados como JSON;
- prueba de replay sin duplicar efectos;
- rollback documentado.

Estado verificado el 2026-07-18: n8n esta `healthy` en `http://localhost:5678`, el administrador esta
creado y hay cero workflows productivos. Ese es el estado correcto hasta que Stage 9 publique los
contratos de eventos.
