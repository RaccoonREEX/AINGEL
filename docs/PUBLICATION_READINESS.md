# Preparación para publicar el repositorio

## Revisión del 2-11-2026 (rama `release/hackathon-submission-2026`)

**Alcance:** todos los objetos alcanzables desde las 36 referencias del repositorio, 1.699 objetos, porque un
repositorio público expone todas las ramas y su historial. No se instaló ningún escáner externo (gitleaks,
trufflehog y detect-secrets no están disponibles en el equipo). Se usó un script propio que informa solo la
ubicación y el tipo, nunca el valor.

**Qué buscó:**
- formatos de claves y tokens (Meta, OpenAI, GitHub, AWS, Google, Slack, JWT, Bearer, PEM, Fernet);
- asignaciones de contraseñas y secretos;
- URL con credenciales;
- nombres de archivo sensibles (`.env`, `.pem`, `.key`, `.sqlite3`, `.local/`, almacenes de claves);
- medios, correos e IP públicas;
- **comparación exacta con los secretos reales del equipo:** la clave de Meta, el archivo de token y la nota SSH del
  Escritorio, y `server-secret`, `encryption.key` y las cuentas de `.local/`. La comparación se hizo dentro del
  script, sin mostrarlos.

| # | Hallazgo | Severidad |
|---|---|---|
| R1 | **Ningún secreto real** aparece en ninguna versión de ninguna rama: ni la clave de Meta, ni tokens, ni la contraseña SSH, ni las claves del servidor o de cifrado, ni las contraseñas de las cuentas de demostración. Nunca se versionaron archivos `.env`, claves, certificados, bases de datos ni `.local/`. | Info |
| R2 | Coincidencias revisadas una a una y benignas: contraseñas sintéticas de prueba (`Synthetic…`, `check…`), una clave Fernet de ceros en `config/test_deployment.py`, URL con credenciales que una prueba de Android verifica que se rechazan, y etiquetas de interfaz en `i18n.ts`. | Info |
| R3 | La IP del VPS, el contenedor del proxy y sus rutas aparecían en `deploy/README.md`, y un nombre de cuenta en `VPS_RECONCILIATION.md`. **Eliminados de esta rama** (`6b9421a`). Siguen en el historial de las ramas anteriores; la IP también se deduce del DNS del dominio. | Baja |
| R4 | **Identidades de los commits:** 78 commits usan el correo Gmail personal del autor. Un commit (`19d626e`, la corrección Docker aplicada en el VPS) tiene como autor `root@` con el nombre de host del proveedor del servidor. Ambos quedarán visibles al publicar. Cambiarlos exige reescribir el historial, que **no se hizo** porque requiere autorización del propietario. | Media (decisión del propietario) |
| R5 | Medios versionados: solo iconos de la app, el isotipo, las fuentes Montserrat y tres capturas de la interfaz de AINGEL Desktop sin datos personales (`web/src/assets/desktop/`). No hay fotos de personas, audio ni vídeo. | Info |
| R6 | Correos en el contenido: dominios de ejemplo (`example.*`), `medlineplus.gov` y el correo del autor de YuNet en su licencia, cuya atribución es obligatoria. | Info |
| R7 | Documentos internos de operación (informes de auditoría, el incidente de la cuenta `prueba.persona`, las validaciones de staging) son públicos si se publica el repositorio. No contienen secretos; el propietario decide si conservarlos. | Baja |

**Licencia:** `LICENSE` es un borrador propietario («todos los derechos reservados, fuente visible para
evaluación»). Faltan el nombre legal del titular, el contacto y la ley aplicable. Las reglas oficiales no exigen una
licencia abierta (ver `HACKATHON_AUDIT_2026.md`).

**Estado:** el repositorio **sigue privado**. Nada se publicó.

---

## Revisión anterior (30-10-2026), conservada como historial

## Preparación para publicar el repositorio — 30 de octubre de 2026

Revisión del worktree `feat/consent-persona-video` (HEAD `cc1084f`) y de **todo el historial** (11 commits,
todas las ramas locales y remotas). No es una auditoría legal. No se publicó nada, no se hizo push ni se
modificó código; los valores secretos no se reproducen aquí.

Severidad: **Alta** = bloquea la publicación · **Media** = resolver antes de publicar · **Baja** = recomendable ·
**Info** = sin acción.

## 1. Secretos y credenciales

Búsqueda en historial (`git grep` sobre `git rev-list --all`) y en los cambios sin confirmar de: claves Meta
(`LLM|…`, `LLM_…`), `sk-`, AWS, GitHub, Slack, Google, Facebook `EAA…`, Hugging Face, claves privadas PEM,
`django-insecure-`, `otpauth://`, `Bearer`, asignaciones de `SECRET_KEY`/`password`/`api_key`/`token`.

| # | Hallazgo | Ubicación | Severidad |
|---|---|---|---|
| S1 | **No se encontró ningún secreto real** en el historial ni en el árbol de trabajo. Nunca se versionaron ni borraron ficheros `.env`, claves, bases de datos ni `.local/` (no hay borrados en el historial). | — | Info |
| S2 | Contraseñas fijas de prueba (solo BD en memoria de tests). | `backend/care/tests.py:354`, `backend/care/test_security.py:24` | Baja (aceptable; son de prueba) |
| S3 | Valores ficticios de entorno en tests: clave de modelo `test-key`, contraseña de BD de prueba, clave Fernet de ceros, hosts `*.example.test`. | `backend/assistance/test_meta_access.py:17`, `backend/config/test_deployment.py:19-33` y otros `test_*.py` | Info |
| S4 | Secretos reales **locales e ignorados**: `.local/server-secret.txt`, `.local/encryption.key`, `.local/demo-accounts.json`, `.local/ui-review-account.json` (worktree principal) y el fichero de clave Meta en el Escritorio. `.gitignore` y `.dockerignore` los excluyen. Riesgo: publicar un ZIP de la carpeta o `git add -f`. | `E:\projects\AINGEL\.local\` | Media (procedimiento) |
| S5 | El lanzador revela el patrón de nombre del fichero de clave en el Escritorio (`^API AINGEL`). | `Start-Aingel.ps1:21` | Baja |
| S6 | `README.md` de `e6c8efa` contiene `DJANGO_SECRET_KEY = '<local-random-secret>'`: es un marcador, no un secreto. | `README.md` (commit `e6c8efa`) | Info |

## 2. Datos personales e infraestructura

| # | Hallazgo | Ubicación | Severidad |
|---|---|---|---|
| P1 | **Correo personal (Gmail) del autor** como autor/committer en 9 commits; los otros 2 usan el alias `noreply` de GitHub. Al publicar queda visible. | `463b50d`, `e6c8efa`, `18f4249`, `de9f308`, `21215bb`, `ee54c5b`, `aae9afb`, `75e05a8`, `cc1084f` | Media (decisión del propietario) |
| P2 | IP pública del VPS, nombre del contenedor proxy, ruta de su Caddyfile y mención de otras aplicaciones alojadas en el mismo servidor. (La IP es deducible del DNS, pero los detalles internos facilitan el reconocimiento.) | `deploy/README.md:14-15` (desde `ee54c5b`) | Media |
| P3 | Dominio del backend alojado incluido en la app y la documentación. Esperable, pero publicar el código lo convierte en objetivo: confirmar que el servidor de pruebas está endurecido y que el registro abierto es intencionado. | `android/.../ApiClient.kt:31`, `deploy/Caddyfile.example`, `deploy/README.md`, `ProtocolTest.kt`, `PublicBackendConnectivityTest.kt` | Baja |
| P4 | Nombres de pila en datos de prueba («David», «Lucía», «Mamá»). Confirmar que no corresponden a familiares reales identificables. | `backend/assistance/test_scene_family.py:13,57`, `backend/care/tests.py:276`, `docs/HOME_AND_SETTINGS.md:23` | Baja |
| P5 | Sin fotos, audio, vídeo, capturas ni datos clínicos en el historial: los únicos binarios versionados son iconos, el isotipo y las fuentes Montserrat. Los informes `docs/*SMOKE*.json` usan material sintético. | — | Info |
| P6 | Dos vídeos LSEC con signantes identificables (CC BY 4.0, consentimiento declarado por el proveedor) existen solo en `.local/datasets/lsec-research/`; nunca se versionaron. Mantenerlos fuera. | `docs/LSEC_RESEARCH_SAMPLES.json` | Info |
| P7 | Modelo de dispositivo de pruebas (Samsung SM-F721B). No es dato personal relevante. | `docs/ANDROID_BUILD_RESULT.json`, `docs/ANDROID_TESTING.md` | Info |

## 3. Licencias y avisos

### Qué se distribuye

| Canal | Contenido de terceros |
|---|---|
| Web (bundle del navegador) | React 19.3.1, ReactDOM, scheduler 0.28.0, three.js 0.184.0 (MIT). Montserrat se carga de Google Fonts. |
| APK Android | 120 artefactos Apache-2.0 (AndroidX, Compose, CameraX 1.4.2, Kotlin, coroutines, OkHttp 4.12.0, Okio…), libyuv (BSD-3-Clause, dentro de `camera-core`), Public Suffix List (MPL-2.0, dentro de OkHttp), Montserrat (OFL-1.1), `assets/hands3d/signs3d.json` (propio). |
| Servidor (no se entrega) | 43 paquetes Python, `meta-sam-parser` (SAM License), YuNet/SFace descargados por `setup_face_models.py` (no están en Git ni en las imágenes; se montan en `/.local/face-models`), índice MedlinePlus, catálogo de clips (vacío). |

Detalle por paquete: [`THIRD_PARTY_INVENTORY.md`](THIRD_PARTY_INVENTORY.md); avisos: [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

### Hallazgos

| # | Hallazgo | Ubicación | Severidad | Estado |
|---|---|---|---|---|
| L1 | **No existe fichero `LICENSE`**: sin él, un repositorio público es «todos los derechos reservados». | raíz | **Alta** | Decisión del propietario (sección 4) |
| L2 | Faltaba el aviso MIT de React/ReactDOM/scheduler, que van en el bundle web. | `THIRD_PARTY_NOTICES.md` | Media | Corregido en raíz y `docs/licenses/React_MIT.txt` |
| L3 | La copia que se sirve con la web está desactualizada (no incluye React ni los avisos nuevos). | `web/public/THIRD_PARTY_NOTICES.txt` | Media | **Pendiente**: copiar el `THIRD_PARTY_NOTICES.md` raíz (fuera del alcance de esta revisión) |
| L4 | El APK no llevaba el texto Apache-2.0 (además `build.gradle.kts` excluye `META-INF/AL2.0`), ni el aviso BSD de libyuv ni el aviso MPL-2.0 de la Public Suffix List. | `android/app/src/main/assets/licenses/THIRD_PARTY_NOTICES.md` | Media | Corregido con textos completos. **Pendiente**: pantalla visible de licencias en la app |
| L5 | Procedencia de los paquetes de diseño propios *AINGEL UI v1.1.1* (orb), *AINGEL Manos y Señas v1.0.0* / motor 0.1.1 / catálogo de señas 1.5.0: se incorporaron en `ee54c5b` (30-10) como paquetes ya versionados. Las reglas exigen identificar el trabajo previo al evento. | `web/src/components/aingel/**`, `android/.../AingelOrb.kt`, `Hands3D.kt`, `AingelSigner.kt` | **Alta (hackathon)** | Confirmar autor y fecha de creación |
| L6 | El isotipo SVG lleva un manifiesto C2PA firmado por Anthropic («Claude provided this file…»). Confirmar autoría/derechos del diseño y si se declara la asistencia de IA. | `web/public/aingel-isotipo.svg` (PNG e iconos sin metadatos) | Baja | Pendiente |
| L7 | Thinking Orbs: verificado MIT, © 2026 Yogesh, en el LICENSE de `yogesharc/thinking-orbs`. El orb se declara portado del paquete AINGEL UI y «sigue el brief» de Thinking Orbs; el aviso se conserva por precaución. | avisos | Info | Correcto |
| L8 | three.js r184: MIT, © 2010-2026 three.js authors (verificado en el LICENSE oficial). | avisos | Info | Correcto |
| L9 | Montserrat: los TTF dicen «Copyright 2011 The Montserrat Project Authors», OFL-1.1, sin nombre reservado. | `res/font/` | Info | Correcto |
| L10 | YuNet (MIT, © 2020 Shiqi Yu) y SFace (Apache-2.0) verificados en OpenCV Zoo `48b10fa5`. No se redistribuyen. Procedencia de los datos de entrenamiento y cumplimiento biométrico (política de uso de Meta, normativa de datos) no auditados. | `docs/FACE_MODELS.json` | Baja | Documentado |
| L11 | `meta-sam-parser`: SAM License (no OSI): incluir el acuerdo si se redistribuye, reconocer su uso en publicaciones, controles de exportación. Solo servidor. | `docs/licenses/meta_sam_parser.txt` | Info | Correcto |
| L12 | Faltaban en el inventario `androidx.lifecycle:lifecycle-service`, `psycopg`/`psycopg-binary` (LGPL-3.0-only) y `redis` (MIT). | inventario | Baja | Corregido |
| L13 | `qrcode` «Other/Proprietary»: el LICENSE real es BSD-3-Clause + MIT (pyqrnative). Los 35 POM Android «por verificar» son Apache-2.0 (POM oficiales). | inventario | Info | Resuelto |
| L14 | Si se publica una imagen Docker del backend, pasa a ser distribución (LGPL de psycopg, MPL de certifi, acuerdo SAM). `redis:7-alpine` es etiqueta flotante (7.4+: RSALv2/SSPLv1; uso interno permitido). | `deploy/` | Baja | Documentado |
| L15 | `web/THIRD_PARTY_NOTICES.md` solo contiene el MIT de Thinking Orbs y duplica la raíz. | `web/` | Baja | Pendiente (unificar o borrar) |
| L16 | `backend/scripts/license_inventory.py` regeneraría el inventario sin las correcciones manuales de hoy. | script | Baja | Pendiente |
| L17 | Señas: diseño propio de AINGEL, **no validado** por personas sordas usuarias de LSEC; no presentarlo como LSEC. No se usa MediaPipe. | `signLexicon.ts`, `signData.ts` | Info | Documentado en código |

Textos de licencia añadidos en `docs/licenses/` (copias de las fuentes oficiales): `Apache-2.0.txt`,
`MPL-2.0.txt`, `libyuv_BSD-3-Clause.txt`, `React_MIT.txt`, `three.js_MIT.txt`, `Thinking_Orbs_MIT.txt`.

## 4. Licencia del código propio de AINGEL (decisión pendiente del propietario)

Reglas del hackathon (`HACKATHON_RULES.md`, `HACKATHON_AUDIT_2026.md`): repositorio **público** obligatorio; el
participante **conserva la titularidad** pero concede al organizador una licencia amplia, mundial, perpetua e
irrevocable sobre la entrega; se permiten componentes de código abierto respetando sus licencias; **no se exige
ninguna licencia concreta**. Todas las dependencias distribuidas son permisivas (MIT, Apache-2.0, BSD, OFL,
MPL-2.0 para datos), compatibles con cualquiera de estas opciones.

| Opción | Qué permite | Ventajas | Inconvenientes |
|---|---|---|---|
| Apache-2.0 | Uso, modificación y uso comercial con aviso; licencia de patentes explícita | Coherente con Android/AndroidX; protege frente a patentes | Exige conservar NOTICE y marcar cambios |
| MIT | Casi todo, con aviso de copyright | Simple, máxima adopción | Sin cláusula de patentes; terceros pueden cerrar derivados |
| AGPL-3.0 | Uso y modificación; quien ofrezca el servicio modificado en red debe publicar su código | Evita SaaS cerrados basados en AINGEL | Frena adopción comercial; complica integrar con código propietario |
| GPL-3.0 | Como AGPL pero sin obligación por uso en red | Copyleft para APK/distribuciones | No cubre el backend como servicio |
| Propietaria / todos los derechos reservados (sin licencia o con aviso explícito) | Solo ver el código en GitHub | Máximo control para una futura startup | No es código abierto; otros no pueden reutilizarlo; revisar si el jurado lo espera |
| Fuente disponible no comercial (p. ej. PolyForm Noncommercial) | Uso no comercial | Protege explotación comercial | No es OSI; menor confianza de la comunidad |

Se puede licenciar distinto el código y los activos (p. ej. código Apache-2.0 y marca/logotipo reservados, o
catálogo de señas CC BY). Antes de elegir: confirmar la titularidad de los paquetes de diseño (L5) y del logotipo (L6).

## 5. Contribuciones desde el 26-10-2026

Todas por un único autor (`RaccoonREEX`); todas están ya en `origin` (privado) salvo el merge `cc1084f`.

| Commit | Fecha | Descripción | Tamaño |
|---|---|---|---|
| `463b50d` | 26-10 18:58 | Auditorías y servicio de escena con pruebas | 29 ficheros |
| `e6c8efa` | 26-10 19:01 | Inferencia Meta real con fixture sintético | 11 ficheros |
| `18f4249` | 27-10 05:14 | Círculos de cuidado, asistencia web, familiares, TOTP | 95 ficheros |
| `de9f308` | 27-10 05:52 | Cliente Android nativo; validación en dispositivo | 38 ficheros |
| `21215bb` | 27-10 18:06 | Compañero personalizado, MedlinePlus, base de clips de señas | 71 ficheros |
| `ee54c5b` | 30-10 00:08 | Preparación para pruebas alojadas; rediseño UI v1.1.1, orb, manos 3D, despliegue | 187 ficheros |
| `aae9afb` | 30-10 05:09 | Restricción de Meta a cuentas aprobadas | 8 ficheros |
| `75e05a8` | 30-10 05:15 | Pruebas sintéticas abiertas explícitas; conectividad Android | 4 ficheros |
| `24e228a`, `6a95298` | 30-10 09:52 | Cabecera Origin para CSRF HTTPS en Android + pruebas | — |
| `cc1084f` | 30-10 20:00 | Merge PR #1 | — |

La rama local `codex/aingel-foundation` sugiere uso de asistentes de IA; las reglas no prohíben asistentes, pero
conviene declararlo si el formulario lo pide. Hay trabajo **sin confirmar** en este worktree y en
`feat/ui-redesign-v1.1.1` (consentimiento, cuota Meta, errores de red): no revisado como entregado.

## 6. Estado de las funciones (según docs y pruebas; no se ejecutaron pruebas en esta revisión)

Pruebas versionadas: 146 funciones `test_*` en backend y 55 `@Test` Android (JVM + instrumentadas). La
documentación aún cita 89 + 13 (27-10): actualizar.

| Implementado y con pruebas automatizadas | Experimental / verificado solo con material sintético | No implementado |
|---|---|---|
| Registro, sesión, CSRF, TOTP/recuperación (`care/test_security.py`, `care/tests.py`) | Descripción de escena (Spark), búsqueda de objetos (SAM 3.1), subtítulos (Voice), compañero: llamadas reales solo con fixtures sintéticos | VoiceStudio / clonación de voz |
| Círculo de cuidado, permisos, invitaciones, rutinas, mensajes, recuerdos con retención | Reconocimiento facial local YuNet/SFace (heurísticas sin calibrar) | Reconocimiento de señas por cámara; modelo de traducción |
| Medios privados y consentimiento (`test_private_media.py`, `web/scripts/test-private-media.mjs`) | Traductor de señas con manos 3D: señas de diseño AINGEL no validadas en LSEC | Catálogo de clips LSEC (vacío) |
| Búsqueda MedlinePlus e importación (`test_communication_resources.py`, `scripts/test_import_medlineplus.py`) | Vigilancia continua, control por voz, plegables (validación manual parcial) | Alarmas en segundo plano / push |
| Control de acceso y cuota Meta (`test_meta_access.py`), ajustes de despliegue (`config/test_deployment.py`) | Evaluación VizWiz (preparada, no ejecutada) | 17 de los 19 idiomas previstos |
| Android: protocolo, CSRF, cookies cifradas, léxico de señas, Hands3D (`ProtocolTest`, `HttpsCsrfOriginTest`, `SessionCookieGateTest`, `SignLexiconTest`, `Hands3DTest`) | | |

## 7. Acciones necesarias antes de hacer público el repositorio

1. **Elegir y añadir `LICENSE`** (y, si procede, `NOTICE` / aviso de marca) — propietario.
2. **Confirmar la procedencia** de los paquetes AINGEL UI v1.1.1 y Manos y Señas v1.0.0 y del isotipo; declarar en
   README/envío qué se creó antes y durante el evento.
3. Decidir sobre el **correo personal en el historial** (P1): aceptarlo o reescribir autores (`git filter-repo
   --mailmap`) antes del primer push público, coordinando con `origin`; configurar el alias `noreply` para lo nuevo.
4. Quitar de `deploy/README.md` la IP y los detalles internos del VPS (P2); decidir si también se reescribe el
   historial (`ee54c5b`) o se acepta.
5. Copiar el `THIRD_PARTY_NOTICES.md` raíz a `web/public/THIRD_PARTY_NOTICES.txt`; unificar o eliminar
   `web/THIRD_PARTY_NOTICES.md`; añadir en la app Android un acceso visible a `assets/licenses/`.
6. Actualizar documentos desactualizados: `KNOWN_LIMITATIONS.md` («repositorio aún local», 89/13 pruebas),
   `HACKATHON_AUDIT_2026.md` (repositorio privado), y `license_inventory.py` con las correcciones manuales.
7. Justo antes de publicar: `git status --ignored` para confirmar que `.local/` y la clave no están rastreados, y
   pasar un escáner de secretos (p. ej. gitleaks) sobre el commit final y todas las ramas que se empujen.
   Al hacer público `RaccoonREEX/AINGEL` se expone todo lo que haya en `origin` (incluida la rama
   `fix/android-https-csrf-origin` y las referencias del PR #1).
8. Confirmar que el servidor alojado (`aingel.mapatechstudio.com`) mantiene `AINGEL_SYNTHETIC_TESTS_ONLY`, la
   lista de cuentas Meta aprobadas y el modo seguro antes de difundir el código.

## 8. Pendiente / fuera de alcance

- Pantalla de licencias Android y sincronización de la copia web (requieren tocar código/ficheros no incluidos aquí).
- Auditoría legal formal; cumplimiento biométrico y de datos de salud; términos de Meta para datos reales.
- Confirmar track, elegibilidad y la autorización promocional del formulario del hackathon.
- Revisar el trabajo sin confirmar de las ramas activas antes de incluirlo en la entrega.
