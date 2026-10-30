# AINGEL: despliegue de prueba para integrar con Caddy existente

Esta propuesta no instala ni modifica nada en el servidor. El modo de IA es
`mock` por defecto; Meta solo se habilita con configuración explícita del servidor. El navegador y Android usan el
mismo origen HTTPS. El backend solo acepta cabeceras reenviadas por el proxy
que se configure explícitamente. Se requiere Docker Engine y Compose v2 en un
host Linux, DNS y un certificado HTTPS del Caddy existente. Los contenedores
no publican puertos al host. La red de datos es interna y PostgreSQL y Redis
solo aceptan conexiones TLS. Antes de usarlo con datos reales se requiere una
revisión de seguridad, privacidad, disponibilidad y recuperación.

## Integración previa, adaptada al servidor real

El VPS identificado es `2.25.176.195`; el proxy central existente es el
contenedor `mapatech-proxy` y su Caddyfile está en `/opt/apps/proxy/Caddyfile`.
Hay otras aplicaciones activas. Estos datos no determinan las redes Docker, las
IP internas, el método de recarga ni la política de logs del servidor: se deben
inspeccionar y validar antes de integrar cualquier cambio. No reemplazar el
contenedor, su Caddyfile completo ni las configuraciones de otros sitios.

1. Confirmar DNS de `aingel.mapatechstudio.com`, el Caddy existente, su método
   de despliegue y si está detrás de otro proxy. El ejemplo presupone Caddy en
   un contenedor con conexión directa de clientes. Un Caddy instalado en el
   host necesita una integración distinta: no usar este snippet sin adaptarlo.
2. Crear una red Docker dedicada a este servicio y adjuntarle solo el Caddy
   autorizado, `backend` y `web`. Asignar y reservar una IP estable al Caddy
   dentro de esa red. No conectar contenedores ajenos: los miembros de la red
   pueden alcanzar el backend. `AINGEL_TRUSTED_PROXY_NETWORKS` debe ser la IP
   efectiva del Caddy como CIDR `/32` (o `/128` para IPv6), verificada desde el
   backend; no usar una red Docker amplia ni asumir que es `127.0.0.1`.
3. Integrar el bloque de `Caddyfile.example` sin reemplazar los demás sitios,
   validar con el Caddy real y comprobar el plan de recarga. Caddy debe
   sobrescribir `X-Real-IP` y `X-Forwarded-Proto`; nunca aceptar estos valores
   del cliente. Si existe CDN o proxy anterior, definir primero su política de
   proxies confiables y adaptar la IP de cliente. Revisar que los logs no
   almacenen datos sensibles, especialmente parámetros de URL.

## Credenciales, TLS y archivos externos

Guardar los archivos fuera del repositorio y del contexto de compilación,
restringidos al administrador y servicios correspondientes. Crear:

* `ca.crt`: CA que firma los certificados de ambos servicios.
* `postgres-tls/server.crt` y `postgres-tls/server.key`: certificado y clave
  con SAN DNS `db`; PostgreSQL verifica los permisos de su clave privada. La
  clave debe pertenecer al usuario del proceso PostgreSQL dentro del contenedor
  y tener modo `0600` (verificar UID/GID de la imagen en el host).
  `postgres-pg_hba.conf` se monta en solo lectura: rechaza TCP sin TLS y
  autoriza con SCRAM únicamente al usuario y base de la aplicación. La regla
  local `trust` es para el socket Unix dentro del contenedor, necesario para
  inicialización y administración local; no compartas ese socket con otros
  contenedores. El healthcheck `pg_isready` sigue usando el socket local.
* `redis-tls/server.crt`, `server.key` y `ca.crt`: certificado con SAN DNS
  `redis`, clave y CA. El usuario Redis debe poder leerlos sin dar acceso a
  otros usuarios del host.
* `postgres-password`: contraseña larga aleatoria, sin salto de línea. Usar la
  misma contraseña en `AINGEL_DB_PASSWORD`; el archivo se usa al inicializar
  un volumen PostgreSQL vacío. Cambiarlo después no cambia automáticamente la
  contraseña en una base existente.
* `redis.acl`: ACL que deshabilite acceso anónimo y active el usuario `default`
  con contraseña. Por ejemplo, una línea `user default on #HASH ~* &* +@all`,
  donde `HASH` es el SHA-256 hexadecimal de una contraseña aleatoria larga. La
  contraseña real va en la URL del backend, no en este archivo ACL. Probar la
  ACL con la versión de Redis elegida antes de exponer el servicio.

Establecer `AINGEL_SECRETS_DIR` a la ruta absoluta de ese directorio y
`AINGEL_BACKEND_ENV_FILE` a un archivo privado fuera del repositorio:

```dotenv
DJANGO_SECRET_KEY=GENERAR_VALOR_ALEATORIO_DE_AL_MENOS_50_CARACTERES
AINGEL_ENCRYPTION_KEY=GENERAR_CLAVE_FERNET_VALIDA
AINGEL_ALLOWED_HOSTS=aingel.mapatechstudio.com
AINGEL_CSRF_TRUSTED_ORIGINS=https://aingel.mapatechstudio.com
AINGEL_WEBSOCKET_ORIGINS=https://aingel.mapatechstudio.com
AINGEL_TRUSTED_PROXY_NETWORKS=IP_REAL_RESERVADA_DEL_CADDY/32
AINGEL_DB_PASSWORD=CONTRASENA_POSTGRES
AINGEL_REDIS_URL=rediss://:CONTRASENA_REDIS_CODIFICADA_URL@redis:6379/0
AINGEL_HSTS_SECONDS=0
```

Generar `AINGEL_ENCRYPTION_KEY` con `python -c 'from cryptography.fernet import
Fernet; print(Fernet.generate_key().decode())'`. Codificar los caracteres
especiales de la contraseña Redis para URL. Las variables se pasan al proceso y
son visibles para administradores Docker: proteger también ese acceso. Nunca
imprimir el archivo de entorno ni registrar `docker compose config` con sus
valores. Mantener la clave Fernet y una copia de los datos de forma segura: si
se pierde la clave, no se pueden recuperar los valores cifrados existentes.
La URL Redis no admite parámetros de consulta; Compose proporciona la CA específica
mediante `AINGEL_REDIS_CA_CERT`. No definir `SSL_CERT_FILE` con solo la CA interna:
eso sustituiría las raíces públicas usadas para HTTPS y WSS hacia Meta. Verificar
la conexión Redis, su certificado y nombre, y la confianza pública de Meta desde
el contenedor antes de habilitar el sitio.

## Meta en entornos controlados

Sin variables de IA adicionales, el backend arranca en `mock` y no usa Meta.
Para una demostración sintética autorizada, añadir **solo al archivo privado del
backend**, sin incluirlo en el repositorio ni en la imagen:

```dotenv
AINGEL_AI_MODE=meta
AINGEL_META_SYNTHETIC_TEST_ACK=1
AINGEL_SYNTHETIC_TESTS_ONLY=1
AINGEL_REAL_DATA=0
MODEL_API_KEY=VALOR_ENTREGADO_POR_EL_PROVEEDOR
```

Para la prueba privada de cámara o audio propios, usar en su lugar:

```dotenv
AINGEL_AI_MODE=meta
AINGEL_PRIVATE_OWN_MEDIA_TEST=1
AINGEL_REAL_DATA=1
AINGEL_SYNTHETIC_TESTS_ONLY=0
MODEL_API_KEY=VALOR_ENTREGADO_POR_EL_PROVEEDOR
```

Son modos separados. Tras modificar el archivo de entorno, hay que recrear el contenedor backend para que reciba sus nuevos valores; reiniciar un contenedor existente no actualiza su entorno.
La prueba privada exige titularidad, permisos de Meta y cámara o micrófono,
y declaración `private_test=true` en cada solicitud; no habilita conversación
personalizada. La bandera sintética es una declaración del cliente y no detecta
contenido real ni de salud; la prueba privada tampoco inspecciona contenido.
Aislar ambos entornos y restringir participantes antes de habilitar Meta: el
registro de la aplicación es público y sus límites por usuario no son un control
de acceso ni una cuota de gasto global. Definir límites reales de consumo con
el proveedor, controlar el presupuesto y validar tráfico de salida a Meta sin
registrar credenciales ni contenido. `MODEL_API_KEY` solo debe estar en el
proceso backend; no usar variables `VITE_`, ni incorporarla a Android, web o
imágenes. El acceso administrativo a Docker también expone variables al proceso.

Definir `AINGEL_ASSETS_DIR` con una ruta externa de recursos de solo lectura y
crear sus subdirectorios `knowledge`, `face-models` y `signs`. Incorporar solo
recursos previamente aprobados y revisados, no copiar el directorio `.local`
completo: contiene credenciales y datos locales. Si faltan los archivos de
índice, modelos o catálogo, las funciones correspondientes no estarán
disponibles. Sus rutas se montan separadamente sin incluirse en la imagen.

## Puesta en marcha y comprobaciones, después de revisar el servidor

Con `AINGEL_SECRETS_DIR`, `AINGEL_ASSETS_DIR`, `AINGEL_BACKEND_ENV_FILE` y `AINGEL_PROXY_NETWORK`
exportadas en el entorno, desde la raíz del repositorio:

```sh
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml up -d db redis
# Esperar a que PostgreSQL esté sano y verificar Redis TLS/ACL.
docker compose -f deploy/compose.yaml run --rm --no-deps backend python manage.py migrate --noinput
docker compose -f deploy/compose.yaml run --rm --no-deps backend python manage.py check --deploy
docker compose -f deploy/compose.yaml up -d backend web
```

Antes de abrir el servicio, comprobar desde la red de datos que PostgreSQL
rechaza una conexión TCP con `sslmode=disable` y acepta la conexión autorizada
con `sslmode=verify-full`, usando la CA y el nombre `db`; comprobar también que
una CA o nombre de servidor incorrectos fallen. El healthcheck local por sí
solo no verifica TLS ni credenciales de red. Estas pruebas aún no se han
ejecutado en el VPS.

Tras validar y recargar Caddy, comprobar HTTPS, `/api/health/`, la SPA, sesión,
CSRF y el handshake de `/ws/captions/` desde el dominio autorizado. Comprobar
también que acceso directo, origen WebSocket no autorizado y cabeceras falsas se
rechazan. Una conexión WebSocket abierta no garantiza transcripción disponible
en modo `mock`. No ejecutar `seed_demo` en un servidor público.

Programar cada día `docker compose -f deploy/compose.yaml exec -T backend
python manage.py purge_expired_memories` con el mismo entorno y supervisar sus
errores. Hacer respaldos cifrados y comprobaciones periódicas de restauración
de PostgreSQL, `private_media` y las claves; coordinar backups de datos y
archivos para que sean coherentes. Redis se usa como caché y no se persiste.
Para actualizar, respaldar, construir, ejecutar migraciones y verificar antes de
recargar; planificar reversión de código y datos. No usar `down -v` sobre datos
que se quieran conservar.

Esta propuesta no ha sido ejecutada en el VPS ni validada contra su topología.
