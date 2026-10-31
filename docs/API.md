# API local v1

Prefijo `/api/v1/`. HTTP-session authentication, cookies HTTP-only y CSRF para escrituras. `GET auth/session/` inicia CSRF y devuelve sesión/desafío pendiente. No se envían secretos Meta al cliente. Todas las respuestas API llevan `Cache-Control: no-store`.

| Método / ruta | Comportamiento |
|---|---|
| GET `/api/health/` | Estado mínimo del proceso |
| POST `auth/register/`, `auth/login/`, `auth/logout/` | Registro/login/logout con CSRF y límites de intentos |
| POST `auth/mfa/verify/` | Completar desafío de cinco minutos; contraseña sola no crea sesión con MFA activo |
| GET `auth/mfa/status/` | Estado de segundo factor, sin secreto |
| POST `auth/mfa/setup/`, `enable/`, `disable/` | QR/TOTP y recuperación; controles descritos en SECURITY_AND_FAMILY.md |
| GET/POST `profiles/` | Perfiles accesibles / crear perfil propio |
| GET/PATCH `profiles/{id}/` | Lectura autorizada / configuración con permiso |
| GET/POST `profiles/{id}/circle/` | Miembros / invitación por el principal; hasta cuatro plazas aceptadas o pendientes |
| POST `invites/accept/` | Aceptar código desde la cuenta destinataria |
| DELETE `profiles/{id}/invitations/{id}/` | Cancelar invitación, principal |
| PATCH/DELETE `profiles/{id}/circle/{member}/` | Cambiar permisos/revocar; miembro puede salir por sí mismo |
| GET/POST `profiles/{id}/routines/` | Horarios y días; crear con permiso de configuración |
| PATCH/DELETE `profiles/{id}/routines/{id}/` | Editar, pausar o eliminar rutina |
| POST/DELETE `profiles/{id}/routines/{id}/confirm/` | Confirmación humana para hoy en la zona del perfil, con autor |
| GET/POST `profiles/{id}/messages/` | Mensajes originales con autor, idioma y fecha |
| DELETE `profiles/{id}/messages/{id}/` | Principal o autor |
| GET/POST `profiles/{id}/memories/` | Lectura con permiso; solo principal puede guardar con `confirmed=true` |
| GET/DELETE `profiles/{id}/memories/{id}/` | Evidencia privada / eliminación por el principal |
| POST `profiles/{id}/ask/` | Herramientas permitidas: `search_memory` con entity, `get_routines`, `get_care_messages` |
| GET `profiles/{id}/audit/` | Historial sin contenido sensible, solo principal |
| GET/POST/DELETE `profiles/{id}/faces/` | Estado / registro propio con consentimiento / revocar registro propio |
| POST `profiles/{id}/faces/consent/` | Principal habilita con contraseña+consentimiento; deshabilitar elimina plantillas |
| POST `profiles/{id}/faces/recognize/` | Comparación local experimental, solo principal y captura consentida |
| POST `scene/`, `locate/` | Imagen sintética → Spark / SAM con clave solo servidor |
| WS `/ws/captions/` | Sesión autenticada, origen permitido y primer mensaje start; PCM24kHz binario y stop |

## Imagen y memoria

Uploads JPEG/PNG/WebP de hasta 5 MiB, máximo 12 millones de píxeles, normalizados a JPEG sin metadatos y lado máximo 1600 px. `scene/` y `locate/` aceptan `image`, `locale` (`es-EC`, `en-US`) y `profile`; `locate/` añade `object_name` de una sola cosa. Sin la autorización de la persona, una prueba sintética solo puede nombrar un fixture del servidor (`fixture`: `shapes` en `scene/`; `red_circle` o `blue_square` en `locate/`; catálogo en `GET synthetic/`), sin imagen ni perfil. El campo `synthetic` se rechaza. Devuelven modo/modelo/latencia; SAM también cajas normalizadas, confianza suministrada por el modelo y máscaras PNG localizadas al recuadro. Se usa la gramática oficial, no regex improvisadas para las máscaras.

Memory POST: entity, location, observed_at ISO8601, confirmed=true, note opcional y evidence opcional. La observación no puede ser futura ni de más de siete días. La fuente está fijada a user_report; no se inventa confianza. Fotos y registros vencidos se ocultan y se purgan mediante la tarea de limpieza. Las cuentas ajenas reciben 404; los permisos insuficientes de un miembro reciben 403.

## Audio

Conectar WebSocket con cookie de sesión y Origin permitido; enviar `{type:'start',locale:'es-EC',synthetic:true}` como JSON. Esperar `{type:'ready',sample_rate:24000}` y enviar PCM16 mono little-endian en tiempo real, hasta 9600 bytes por frame. El servidor añade la autorización Meta a su handshake, sin exponerla. Los eventos transcript parciales reemplazan la hipótesis previa; speechComplete finaliza por turnId. `{type:'stop'}` drena resultados y cierra. Una sesión por usuario, diez minutos máximo, sin persistencia.

Los límites distribuidos, paginación completa, política de sesión, OpenAPI y versión de contratos Android son trabajo previo a producción. Esta API aún no representa un servicio público desplegado.

## Registro facial de varias fotos

`POST profiles/{id}/faces/` recibe multipart con uno a tres campos repetidos `image`, `display_name`, `consent=true`, `own_photo=true`. Solo la cuenta del propio familiar adulto aceptado puede registrar sus fotos. Tamaño combinado máximo 5 MiB. Rechaza fotos normalizadas idénticas, falta de un único rostro claro, nitidez Laplaciana <30 y similitud entre tomas <0.4. Son controles heurísticos pendientes de calibración. El lote se valida antes de reemplazar el registro anterior y la escritura vuelve a verificar consentimiento/membresía bajo bloqueo del perfil.

La plantilla cifrada v2 contiene hasta tres vectores normalizados. Las plantillas anteriores de un vector siguen siendo legibles. GET y POST exponen `sample_count`, nunca vectores. La consulta compara un puntaje por persona (media de las dos mejores tomas disponibles), exige 0.55 y margen 0.10 respecto a la siguiente persona; las capturas borrosas se abstienen. Más tomas de una persona no cuentan como identidades adicionales. No hay resultados de precisión verificados ni liveness.

## Comunicación y búsqueda de información

`GET/PATCH profiles/{id}/communication/` maneja opciones explícitas de nombre, trato, longitud de saludo, ritmo, presentación, apoyo, lengua de señas y notas. El círculo puede leer y solo el principal o un miembro con permiso de configuración puede editar. El backend valida valores y audita cambios sin contenido. El ajuste de lengua de señas no implica traducción implementada.

`POST profiles/{id}/resources/search/` recibe JSON `{q,lang}` (es/en), busca por título en el índice local de resúmenes MedlinePlus y devuelve hasta cinco resultados con título, texto, origen, URL y fecha. No registra la consulta ni la envía a Meta; sin resultado devuelve `[]`, y sin índice devuelve 503 `knowledge_not_installed`. La salida es material educativo atribuido, no diagnóstico ni recomendación personalizada. Preparación: `backend/scripts/import_medlineplus.py`.

## Clips revisados de lengua de señas

`POST profiles/{id}/signs/lookup/` recibe `{text,language}` con una frase completa final y lengua `lsec` o `asl`. La preferencia `other` se guarda, pero no activa búsquedas hasta identificar una lengua concreta. La coincidencia es exacta tras normalizar espacios y mayúsculas; conserva acentos, puntuación, negación y orden. Sin catálogo o coincidencia devuelve `{available:false}`. La consulta no se registra ni se envía a Meta. Solo se aceptan perfiles autorizados.

Con una coincidencia, devuelve `available:true` y metadatos de atribución; `GET profiles/{id}/signs/clips/{clip_id}/` entrega el vídeo MP4 local verificado bajo la misma autorización, máximo 20 MiB y no-store. El catálogo `.local/signs/catalog.json` exige versión, frase, idioma, indicación de revisión, revisor/fecha, fuente, atribución, licencia y hash SHA-256; el vídeo debe estar en `.local/signs/clips/<sha256>.mp4`. Un catálogo o archivo inválido devuelve 503, jamás una traducción aproximada. El catálogo de AINGEL está vacío: todavía no hay clips disponibles ni interpretación de conversaciones abiertas.

## Pregunta conversacional sintética

`POST profiles/{id}/companion/chat/` acepta JSON `{text,synthetic:true}` de hasta 1.000 caracteres, y opcionalmente `topic_title` y `topic_lang` de una fuente MedlinePlus seleccionada por título exacto. La solicitud al proveedor contiene la pregunta declarada sintética, el extracto público opcional y las preferencias categóricas; no se añaden nombre, notas, recuerdos, mensajes ni historial del perfil. Devuelve texto, modo/modelo, latencia y fuente seleccionada si existe. No se registra la pregunta. La casilla es una declaración del usuario, no un detector de datos reales; no usarlo con datos personales. La salida del modelo puede equivocarse y no sustituye atención clínica.
