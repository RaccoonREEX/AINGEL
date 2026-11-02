# AINGEL: acceso público con consentimiento (31-10-2026)

Rama `feat/aingel3-public-access`, PR #12, apilada sobre #11 (todos los PR apuntan a `main`). No está fusionada ni desplegada.

## Política

- **Elegibilidad:** puede usar las funciones de Meta toda cuenta activa que haya declarado ser mayor de edad y no
  estar en un territorio restringido por Meta (ver «Territorios restringidos»). Es el valor por defecto,
  `AINGEL_META_ACCESS=public`.
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

## Territorios restringidos por Meta (`care/territory.py`)

La política de Meta (12-10-2026, §3) prohíbe ofrecer productos integrados, o permitir a sabiendas el acceso, a
personas ubicadas en: Afganistán, Bielorrusia, Camboya, China (incluidos Hong Kong y Macao), Cuba, Eritrea, Etiopía,
Haití, Irán, Irak, Libia, Myanmar, Nicaragua, Corea del Norte, Pakistán, Rusia, Somalia, Siria, las regiones de
Crimea, Donetsk y Luhansk de Ucrania, Venezuela y Sáhara Occidental.

- **Declaración, como la de 18+:** en el registro, la persona responde «¿Dónde estás?» con dos opciones.
  - «Estoy en uno de ellos» no crea la cuenta (403 `territory_restricted`).
  - **Solo se guarda la respuesta** y la versión de la política, nunca el país ni la ubicación (`AccountPolicy`,
    migración `care.0010`).
- **Cuentas existentes:** responden una vez en una pantalla como la de 18+ (`POST auth/territory/`). Pueden cambiar la
  respuesta si se mudan.
- **Mientras falte la respuesta, o si declararon estar dentro:**
  - todo endpoint de Meta, websockets incluidos, se rechaza antes de llamar a Meta, con
    `territory_declaration_required` o `meta_territory_restricted`;
  - la web y Android mantienen AINGEL cerrado y explican por qué.
- **Si la política cambia:** basta subir `POLICY_VERSION` y todas las cuentas vuelven a responder.
- **Control técnico opcional:**
  - si el proxy inverso añade el país de la conexión (por ejemplo, con un módulo GeoIP), `AINGEL_GEO_COUNTRY_HEADER`
    nombra esa cabecera y también se rechazan los países restringidos;
  - sin configurar, la cabecera se ignora, y `deploy/Caddyfile.example` la elimina para que un cliente no pueda
    enviarla;
  - Crimea, Donetsk y Luhansk no se distinguen del resto de Ucrania por código de país, así que para esas regiones
    solo vale la declaración.
- **Lo que no hace:** no hay aprobación manual ni lista de cuentas. Las cuentas elegibles mantienen el acceso
  general.
- **En modo local (`mock`)** no se exige nada de esto, porque no se llama a Meta.

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
  - `AINGEL_GEO_COUNTRY_HEADER` que no sea un nombre de cabecera válido;
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
| Gasto diario por cuenta | `AINGEL_META_USER_DAILY_USD` | sin límite | Opcional; **estimación parcial**, se calcula desde el registro de consumo (ver abajo) |
| Presupuesto total | `AINGEL_META_BUDGET_USD` | sin límite | Opcional; misma estimación parcial |

- **Cómo se cuentan:** los contadores de plataforma y de cuenta se comprueban y se suman **en un solo script de
  Redis**, que es atómico entre procesos.
- **Unidades:** una descripción profunda cuenta como 3 llamadas.
- **Sin cuenta:** en producción, una llamada sin cuenta se rechaza (`meta_account_required`).
- **Throttles de DRF:** siguen activos, por ejemplo 12/min para visión. La cuota de Meta es otra capa.
- **Calidad:** no se tocaron niveles, presupuestos de tokens ni razonamiento.
- **Si Astra tiene configurados los antiguos valores 10/100 globales,** debe subirlos. Si no, toda la plataforma
  compartiría 100 llamadas al día.

### Registro de consumo (`assistance/usage.py`, tabla `MetaUsage`)

- **A quién se cobra:** cada llamada a Meta se registra **a la cuenta que la hizo**.
  - La cuenta viene del usuario autenticado en el servidor (`request.user`, fijado por `meta_account_denial`).
  - Nunca de un identificador que envíe el cliente.
  - Antes, las filas de escena, conversación, búsqueda de objetos, vídeo y señas quedaban sin cuenta, y el tope
    diario por cuenta no las veía.
- **Precios:** son los Standard de Meta, comprobados el 31-10-2026 en
  [la página de precios](https://dev.meta.ai/docs/pricing-rate-limits).

| Modelo | Cómo factura Meta | Cómo lo registra AINGEL |
|---|---|---|
| `muse-spark-1.3` | Tokens: entrada 1,25, entrada en caché 0,15 y salida 4,25 USD por millón; búsqueda web 2,50 USD por 1.000 consultas | Tokens del `usage` de la respuesta y número de `web_search_call` |
| `sam-3.1` | 2,50 USD por 1.000 imágenes | 1 imagen por petición (AINGEL envía una) |
| `muse-voice-transcribe-1.0` | 0,18 USD por hora de audio, en segundos enteros redondeados hacia abajo | Segundos de audio PCM reenviados a Meta, en una fila por sesión de subtítulos |

- **Visión profunda:** cada una de sus tres llamadas se registra en cuanto Meta responde. Si una etapa posterior
  falla, el consumo de las anteriores no se pierde.
- **Qué guarda la tabla:** solo unidades facturadas: tokens, imágenes, segundos y búsquedas. Nunca la imagen, la
  pregunta, el audio ni la respuesta.
- **Es una estimación parcial, no la factura de Meta:**
  - una petición que falla antes de que Meta responda (red, tiempo de espera) no se puede contar;
  - el registro empieza vacío;
  - la consola de facturación de Meta es la referencia.

  Por eso los topes monetarios **reducen el riesgo, pero no garantizan** que no se gaste más.

## Pruebas

- **Backend:** `manage.py test` ejecuta 321 pruebas: **314 correctas** y 7 omitidas. Las omitidas necesitan Redis real
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

- **Registro de consumo** (`assistance/test_usage_ledger.py`): por las rutas reales, con Meta simulado y comprobando
  las filas reales de `MetaUsage`:
  - escena, búsqueda de objetos, conversación y vídeo se registran a la cuenta que pidió;
  - se ignora un ID enviado por el cliente;
  - el tope diario cuenta todas las funciones;
  - precios de SAM, Voice y búsqueda web;
  - los subtítulos registran sus segundos y se rechazan si se alcanzó el tope;
  - la visión profunda conserva las etapas ya respondidas.
- **Territorios** (`care/test_territory.py`):
  - registro dentro, sin declarar o con una versión vieja: no se crea la cuenta;
  - cuenta existente que declara dentro: Meta cerrado hasta cambiar la respuesta;
  - la cabecera del proxy se ignora sin configurar y bloquea países restringidos si está configurada;
  - los subtítulos desde un país restringido no llegan a Meta;
  - las cuentas elegibles no necesitan lista;
  - el modo local no se ve afectado.
- **Web:** `npm run test:territory`. Comprobado también en el navegador contra el servidor local en modo `mock`:
  registro dentro y fuera, y la pantalla para cuentas existentes.
- **Modalidad:** `test_meta_modality` comprueba que solo se usan modelos Standard.
- **Modos de producción:** `config/test_deployment.test_production_modes`.
- **Escritorio:** 98 comprobaciones. Los subtítulos declaran `source: system`.
- **Android:** `assembleDebug`, `assembleDebugAndroidTest`, 85 pruebas unitarias (incluida `TerritoryTest`) y
  `lintDebug` pasan en este equipo con Gradle 8.14.3 (ver la sección siguiente). No se ejecutó en un dispositivo.

## Android y Gradle (diagnóstico del fallo de Astra)

En este equipo, `./gradlew assembleDebug testDebugUnitTest` termina con **BUILD SUCCESSFUL**, con Gradle 8.14.3, el
JBR 21 de Android Studio y las dependencias ya en caché. El fallo de Astra fue de conexión: el wrapper descarga
`gradle-8.14.3-bin.zip` de services.gradle.org, y las dependencias vienen de Google Maven y Maven Central.

**No es un error del código.** Para compilar en el VPS o en CI hace falta salida a esos dominios, o una caché de
Gradle precargada con `--offline`.

## Riesgos y pendientes

1. **Territorios restringidos por Meta:**
   - Ya hay una autodeclaración obligatoria y un bloqueo en el servidor.
   - **Límite:** una declaración falsa no se detecta.
   - El control por país de la conexión **solo funciona si el proxy proporciona una fuente GeoIP**, y hoy no está
     configurado; activarlo es decisión de despliegue.
   - Las regiones de Ucrania solo se cubren con la declaración.
2. **Topes monetarios:** son una estimación parcial. No cuentan las peticiones que fallan antes de que Meta responda,
   y la factura de Meta manda.
3. **Subtítulos con terceros:** el aviso y la finalidad lo explican, pero AINGEL no puede comprobar que los demás
   estén informados.
4. **Retención en Meta:** no hay retención cero contratada.
5. **Cuotas con Redis real:** las 7 pruebas están escritas y probadas con Redis simulado. **Falta ejecutarlas contra
   un Redis real aislado**, a cargo de Astra en el VPS, **antes de activar el acceso público en producción**. El
   procedimiento, sin créditos de Meta ni datos de usuarios, está en `docs/REDIS_REAL_VALIDATION.md`.
6. **Código que corre en el VPS:** `docs/VPS_RECONCILIATION.md` explica cómo reconciliarlo sin tocar producción.
