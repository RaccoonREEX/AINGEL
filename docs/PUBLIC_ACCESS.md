# AINGEL: acceso público con consentimiento (31-10-2026)

Rama `feat/aingel3-public-access`, PR #12, apilada sobre #11 (todos los PR apuntan a `main`). No está fusionada ni desplegada.

## Política

- **Elegibilidad:** puede usar las funciones de Meta toda cuenta activa que haya declarado ser mayor de edad al
  registrarse. Es el valor por defecto, `AINGEL_META_ACCESS=public`.
  - No hay listas de cuentas, aprobación manual, cuentas compartidas ni límites de cuentas registradas.
  - La lista de IDs (`AINGEL_META_ACCESS=allowlist` con `AINGEL_META_ALLOWED_USER_IDS`) queda solo como modo
    explícito para pruebas escalonadas, nunca por defecto y sin comodín `*`.
- **Autorización:** la elegibilidad **no es consentimiento**. Cada petición solo envía a Meta los datos para los que
  la propia persona aceptó **cada** finalidad. Nada se concede automáticamente. La persona decide una por una y
  puede revocar en cualquier momento.
- **Revocación:** cada revocación incrementa `consent_epoch`. Con eso:
  - las operaciones en curso descartan su respuesta (409 `consent_changed`);
  - las sesiones de imagen y de documento se borran;
  - los subtítulos se detienen al comprobar los permisos, que se revisan cada 5 s.

### Finalidades: qué se envía a Meta y qué se conserva

| Finalidad | Qué cubre | Qué conserva AINGEL |
|---|---|---|
| `meta_conversation` | Preguntas a AINGEL y frases para traducir a señas | Historial según la conversación existente |
| `camera_local` + `meta_photos` | Fotos de la cámara o de la galería para describir o buscar objetos | La imagen, cifrada, hasta 15 min, para preguntas de seguimiento |
| `camera_local` + `meta_video` | Clips de la vigilancia continua (experimental) | Nada |
| `microphone_local` + `meta_voice` | La voz propia, para subtítulos | Nada |
| **`meta_screen`** (nuevo) | Capturas de pantalla o de ventanas en AINGEL Desktop, **solo cuando se piden** | La imagen, cifrada, hasta 15 min |
| **`meta_documents`** (nuevo) | PDF y fotos de páginas. El texto se lee sin Meta; las transcripciones y explicaciones sí van a Meta. | El documento, cifrado, hasta 2 h |
| **`meta_meeting_audio`** (nuevo) | El audio que reproduce la computadora (reuniones, vídeos), **con voces de terceros** que deben estar informados | Nada; tampoco la transcripción |
| `profile_personalization` | Apoyos indicados y alergias, junto con las preguntas | — |
| `face_local` | Reconocimiento familiar en el servidor de AINGEL, no en Meta. **Sigue desactivado** (`AINGEL_FACE_RECOGNITION_ENABLED=0`). | — |

**Por qué hacían falta finalidades nuevas:**
- Capturar una pantalla no es usar la cámara.
- Un documento no es una foto de la cámara.
- El audio de una reunión con otras personas no es la voz propia.

Las aplicaciones web y Android muestran las finalidades a partir de la lista del servidor, así que las nuevas
aparecen sin cambios en los clientes. Cada una tiene un título y una frase, accesibles con lector de pantalla, y se
deciden en la misma pantalla de permisos.

**Modalidad de Meta:** solo se usan modelos Standard. Meta no entrena con ese contenido y puede conservarlo según
§4.4 (ver `docs/META_MODEL_API_TERMS.md`). El aviso que acompaña a los permisos lo explica.

## Modos del servidor (validados al arrancar, `config/settings.py`)

| Modo | `AI_MODE` | `REAL_DATA` | `SYNTHETIC_TESTS_ONLY` | `PRIVATE_OWN_MEDIA_TEST` |
|---|---|---|---|---|
| Desarrollo local | `mock` | `0` | `1` | `0` |
| Pruebas sintéticas con Meta | `meta` | `0` | `1` + `AINGEL_META_SYNTHETIC_TEST_ACK=1` | `0` |
| **Producción con consentimiento (objetivo)** | `meta` | `1` | `0` | `0` |
| Prueba privada del propietario | `meta` | `1` | `0` | `1` |

- **Se rechaza al arrancar:**
  - `REAL_DATA=1` con modo `mock` o con `SYNTHETIC_TESTS_ONLY=1`;
  - `PRIVATE_OWN_MEDIA_TEST=1` sin `REAL_DATA=1`;
  - `META_ACCESS` desconocido, o `allowlist` sin IDs numéricos;
  - falta de `MODEL_API_KEY` con Meta.
- **En la prueba privada,** `meta_allowed` sigue sin habilitar el texto personal genérico, como antes. Para la
  producción pública hay que usar `PRIVATE_OWN_MEDIA_TEST=0`.

## Cuotas (protegen la disponibilidad, no recortan respuestas)

| Límite | Variable | Por defecto | Alcance |
|---|---|---|---|
| Llamadas por minuto, plataforma | `AINGEL_META_LIMIT_PER_MINUTE` | 60 | Red de seguridad común |
| Llamadas por día, plataforma | `AINGEL_META_LIMIT_PER_DAY` | 5000 | Red de seguridad común |
| Llamadas por minuto, **por cuenta** | `AINGEL_META_USER_LIMIT_PER_MINUTE` | 12 | Cada cuenta |
| Llamadas por día, **por cuenta** | `AINGEL_META_USER_LIMIT_PER_DAY` | 300 | Cada cuenta |
| Peticiones pesadas simultáneas | — | 1 por cuenta | Visión y documentos (429 `meta_busy`) |
| Gasto diario por cuenta | `AINGEL_META_USER_DAILY_USD` | sin límite | Opcional; se calcula desde el registro de consumo |
| Presupuesto total | `AINGEL_META_BUDGET_USD` | sin límite | Opcional |

- **Cómo se cuentan:** los contadores de plataforma y de cuenta se comprueban y se suman **en un solo script de
  Redis**, que es atómico entre procesos.
- **Unidades:** una descripción profunda cuenta como 3 llamadas.
- **Sin cuenta:** en producción, una llamada sin cuenta se rechaza (`meta_account_required`).
- **Throttles de DRF:** siguen activos, por ejemplo 12/min para visión. La cuota de Meta es otra capa.
- **Calidad:** no se tocaron niveles, presupuestos de tokens ni razonamiento.
- **Si Astra tiene configurados los antiguos valores 10/100 globales,** debe subirlos. Si no, toda la plataforma
  compartiría 100 llamadas al día.

## Pruebas

- **Backend:** `manage.py test` ejecuta 297 pruebas: **290 correctas** y 7 omitidas. Las omitidas necesitan Redis real
  (pendientes de validar en el VPS por Astra, ver `docs/REDIS_REAL_VALIDATION.md`); con
  `AINGEL_TEST_REDIS_URL` y `AINGEL_TEST_REDIS_ISOLATED=1` las ejecuta Astra, incluida la nueva
  `test_meta_quota_per_account_on_real_redis`, que prueba varias cuentas.
- **Pruebas obligatorias** en `assistance/test_public_access.py`, con cuentas nuevas y por las rutas reales:

| Prueba | Qué comprueba |
|---|---|
| Usuario nuevo | Se registra, declara su edad, crea su perfil, concede conversación y fotos, y usa Meta sin ninguna lista |
| Permisos parciales | Conversa, pero las fotos se rechazan y no salen del servidor |
| Sin decisión | No se envía nada |
| Revocación | Revocar durante una sesión detiene el envío y borra la imagen |
| Edad mínima | Sin la declaración, el registro se rechaza. `test_meta_access` cubre también una cuenta existente sin declaración. |
| Privacidad | La pantalla y los documentos exigen su propio permiso, no el de la cámara; una cuenta no accede al perfil de otra |
| Cuotas | Cada cuenta usa sus propias claves y comparte las de plataforma; una descripción a la vez; tope diario por cuenta |

- **Modalidad:** `test_meta_modality` comprueba que solo se usan modelos Standard.
- **Modos de producción:** `config/test_deployment.test_production_modes`.
- **Escritorio:** 97 comprobaciones. Los subtítulos declaran `source: system`.
- **Android:** `assembleDebug` y las pruebas unitarias pasan en este equipo con Gradle 8.14.3 (ver la sección
  siguiente).

## Android y Gradle (diagnóstico del fallo de Astra)

En este equipo, `./gradlew assembleDebug testDebugUnitTest` termina con **BUILD SUCCESSFUL**, con Gradle 8.14.3, el
JBR 21 de Android Studio y las dependencias ya en caché. El fallo de Astra fue de conexión: el wrapper descarga
`gradle-8.14.3-bin.zip` de services.gradle.org, y las dependencias vienen de Google Maven y Maven Central.

**No es un error del código.** Para compilar en el VPS o en CI hace falta salida a esos dominios, o una caché de
Gradle precargada con `--offline`.

## Riesgos y pendientes

1. **Territorios restringidos por Meta (§3 de la política geográfica):**
   - **Riesgo:** AINGEL no pregunta el país de residencia, así que no puede negarse a quien declare vivir en uno de
     esos territorios.
   - **Propuesta:** una declaración de país en el registro y un bloqueo de Meta para los países restringidos. Afecta
     a la web y a Android, y queda pendiente.
2. **Subtítulos con terceros:** el aviso y la finalidad lo explican, pero AINGEL no puede comprobar que los demás
   estén informados.
3. **Retención en Meta:** no hay retención cero contratada.
4. **Cuotas con Redis real:** las 7 pruebas están escritas y probadas con Redis simulado. **Falta ejecutarlas contra
   un Redis real aislado**, a cargo de Astra en el VPS, **antes de activar el acceso público en producción**. El
   procedimiento, sin créditos de Meta ni datos de usuarios, está en `docs/REDIS_REAL_VALIDATION.md`.
5. **Código que corre en el VPS:** `docs/VPS_RECONCILIATION.md` explica cómo reconciliarlo sin tocar producción.
