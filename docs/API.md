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

Uploads JPEG/PNG/WebP de hasta 5 MiB, máximo 12 millones de píxeles, normalizados a JPEG sin metadatos y lado máximo 1600 px. `scene/` y `locate/` aceptan `image`, `locale` (`es-EC`, `en-US`), `synthetic=true`; `locate/` añade `object_name` de una sola cosa. Devuelven modo/modelo/latencia; SAM también cajas normalizadas, confianza suministrada por el modelo y máscaras PNG localizadas al recuadro. Se usa la gramática oficial, no regex improvisadas para las máscaras.

Memory POST: entity, location, observed_at ISO8601, confirmed=true, note opcional y evidence opcional. La observación no puede ser futura ni de más de siete días. La fuente está fijada a user_report; no se inventa confianza. Fotos y registros vencidos se ocultan y se purgan mediante la tarea de limpieza. Las cuentas ajenas reciben 404; los permisos insuficientes de un miembro reciben 403.

## Audio

Conectar WebSocket con cookie de sesión y Origin permitido; enviar `{type:'start',locale:'es-EC',synthetic:true}` como JSON. Esperar `{type:'ready',sample_rate:24000}` y enviar PCM16 mono little-endian en tiempo real, hasta 9600 bytes por frame. El servidor añade la autorización Meta a su handshake, sin exponerla. Los eventos transcript parciales reemplazan la hipótesis previa; speechComplete finaliza por turnId. `{type:'stop'}` drena resultados y cierra. Una sesión por usuario, diez minutos máximo, sin persistencia.

Los límites distribuidos, paginación completa, política de sesión, OpenAPI y versión de contratos Android son trabajo previo a producción. Esta API aún no representa un servicio público desplegado.
