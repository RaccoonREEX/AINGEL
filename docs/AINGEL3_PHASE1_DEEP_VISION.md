# AINGEL 3.0 · Fase 1: visión profunda (31-10-2026)

Rama `feat/aingel3-deep-vision`, apilada sobre `feat/sign-recognition-experimental` (PR #5) y
`fix/android-capture-messages` (PR #4). No está fusionada ni desplegada. Las fases 2 a 6 (escritorio Windows,
documentos, audio del sistema, señas validadas, instalador) **no están hechas**: ver «Pendiente».

## Qué cambia

| Parte | Cambio |
|---|---|
| Prompt maestro (`assistance/persona.py`) | Versión `2026-10-31`. La identidad (SEED) y 13 políticas separadas en `POLICIES`: visión, niveles, continuidad, rostros, dibujos, modo académico, documentos, pantalla, audio, movilidad, personas, estructura oral y revisión final. Cada endpoint adjunta solo las que necesita. `VISION_RULES` se mantiene para la descripción breve y el vídeo. Un nivel de detalle pedido explícitamente prevalece sobre la preferencia «respuestas breves». |
| Motor de visión (`assistance/vision.py`) | Cuatro niveles, siete tareas visuales, diez zonas, sesiones de seguimiento y texto apto para voz (sin Markdown). |
| API | `POST /api/v1/vision/`: campos `question`, `detail_level`, `visual_task`, `focus_region`, `source_kind`, `session`. `DELETE /api/v1/vision/sessions/<token>/`. `scene/` (vigilancia y modo «Describir») sigue igual. |
| Consumo (`assistance/usage.py`, modelo `MetaUsage`) | Cada llamada a Meta registra tokens, latencia y coste estimado, pero nunca el contenido. Con `AINGEL_META_BUDGET_USD`, las llamadas se detienen al llegar al presupuesto. `python manage.py meta_usage` muestra el resumen. |
| Imágenes sintéticas | El servidor dibuja: un perro, un dibujo ambiguo, un retrato ilustrado ficticio, una página de libro ficticio y un gráfico de barras. |
| Android | El botón «Describir lo que ves» usa la visión profunda. Una pregunta justo después de una respuesta visual se responde sobre la misma imagen. Las respuestas visuales ofrecen «Más detalle» y «Explorar a fondo». La voz lee los textos largos por partes. Las peticiones de visión esperan hasta 180 s. |
| Web | La pantalla «Ver» permite elegir nivel, hacer una pregunta (solo con imagen propia), elegir las imágenes sintéticas y seguir preguntando por zona o nivel. También tiene «Terminar con esta imagen» y lectura por partes. El orbe de inicio usa la visión profunda y borra la sesión en el acto. |
| Señas por cámara | Esfuerzo `low` con 2500 tokens, en lugar de `minimal` con 600, porque es una tarea visual compleja. |

### Niveles (parámetros verificados en la documentación de Meta y con una llamada real)

| Nivel | `reasoning.effort` | `max_output_tokens` | Llamadas |
|---|---|---|---|
| brief | low | 2500 | 1 |
| standard | medium | 5000 | 1 |
| detailed | high | 10000 | 1 |
| deep | high | 8000 en cada paso + 12000 en la síntesis | 3 |

- **Tokens de razonamiento:** cuentan dentro de `max_output_tokens`, así que los límites dejan espacio para pensar y
  para escribir.
- **Nivel deep:**
  1. Identificación global e imagen entera con cinco recortes ampliados (cuatro cuadrantes y el centro), en
     paralelo.
  2. Una síntesis que contrasta esas notas con la imagen.
- **Clasificación de la pregunta:**
  - «a detalle» y «a fondo» → `deep`.
  - «¿Y sus ojos?» → tarea `face`.
  - «arriba a la izquierda» → zona `top_left`.
  - «¿Qué hay en el fondo?» → zona `background`.
- **Sesión:** en un seguimiento, un dibujo sigue siendo dibujo.
- **Constantes:** `store=false` siempre. Se usan el modelo `muse-spark-1.3` y el endpoint `https://api.meta.ai/v1/responses`.

### Privacidad y consentimiento

- **Imágenes sintéticas:** solo admiten el id, el nivel y la zona. Una pregunta escrita es contenido libre y se
  rechaza con una imagen sintética (`synthetic_fixture_only`), igual que una foto o un perfil.
- **Imagen real:**
  - Exige las mismas autorizaciones que describir una foto.
  - Cada seguimiento vuelve a comprobar el rechazo de cámara, la época de consentimiento y los permisos.
  - Si alguno cambió, la sesión y su imagen se borran: `camera_consent_revoked` o `consent_changed` (409).
  - Una revocación mientras Meta mira descarta la respuesta y la sesión.
- **Sesión:**
  - La imagen normalizada (JPEG sin EXIF) se cifra con Fernet en la caché durante un máximo de 15 minutos.
  - Pertenece a una sola cuenta; otra cuenta recibe 404.
  - La clave del caché es un hash del token, y el token no se guarda.
  - «Terminar con esta imagen» o «borrar conversación» la eliminan en el acto.
- **Rostros:**
  - Se describen rasgos observables.
  - No se atribuye identidad por parecido y no se infiere origen étnico, diagnóstico, emoción interna ni
    personalidad.
  - El reconocimiento facial sigue apagado: este cambio no lo toca.
- **Dibujos y modo académico:**
  - La respuesta empieza por lo que representa el dibujo.
  - Separa «Observaciones visuales» de «Interpretaciones teóricas», y estas solo aparecen si se piden.
  - Nunca diagnostica.
- **Movilidad:** se mantiene la regla en código (`vision_guard`), y el aviso de no moverse guiándose por la
  respuesta solo aparece en escenas.

## Pruebas ejecutadas

- **Backend:** `manage.py test` da 254 correctas, con 6 omitidas que necesitan Redis real. Las nuevas están en
  `assistance/test_vision.py` (21):
  - esfuerzo y límite por nivel;
  - los tres pasos de `deep`, con 1 + 5 imágenes;
  - las políticas de rostro, dibujo, modo académico y documento llegan al prompt;
  - recorte de zona;
  - ningún marcador privado en las peticiones sintéticas;
  - una pregunta junto a una imagen sintética se rechaza sin enviar nada;
  - el seguimiento reutiliza la misma imagen y conserva la tarea;
  - otra cuenta no puede usar la sesión;
  - cierre con DELETE;
  - la sesión está cifrada;
  - registro de consumo y coste exacto;
  - el presupuesto detiene llamadas;
  - una respuesta incompleta no se muestra pero sí se contabiliza;
  - la regla de movilidad;
  - autorización real, revocación de cámara y de fotos que borra la sesión;
  - revocación durante la llamada.
- **Android:** `assembleDebug testDebugUnitTest lintDebug` da 79 pruebas unitarias correctas (incluye
  `VisionTest`) y 0 errores de lint. No se probó en el teléfono: hace falta el backend desplegado.
- **Web:** se ejecutaron:
  - `typecheck`;
  - `build`;
  - `test:vision`, que es nuevo;
  - `test:private-media`, `test:synthetic-conversation`, `test:browser-speech` y `test:revocation`.

  Además, se probó en el navegador contra el backend local en modo de prueba: dibujo del perro en «A fondo», seguimiento
  «Arriba a la derecha» y «Terminar» (DELETE 204).

### Prueba real con Meta, solo con imágenes sintéticas del servidor

`es-EC`, preferencias ficticias por defecto (frases cortas). Coste total registrado: **0,163 USD**.

| Caso | Nivel | Latencia | Tokens de salida (razonamiento) | Coste | Resultado |
|---|---|---|---|---|---|
| B: dibujo de perro | standard | 9,9 s | 1948 (1702) | 0,0108 | Empieza con «Veo un perro.». Describe cabeza, orejas, hocico, lengua, collar, cuatro patas, cola, suelo, tipo de línea y relleno. |
| B: dibujo de perro | deep (3 pasos) | 56,6 s | 14420 (13235) | 0,0712 | «Veo un perro». Recorre la cabeza, el cuerpo, las patas, la composición y las dudas reales, como el borde del collar. |
| C: dibujo ambiguo | standard | 7,7 s | 1366 (1176) | 0,0083 | «Formas alargadas y redondeadas superpuestas, que recuerdan a clips… No es seguro si quiere ser un objeto concreto». |
| C: modo académico | detailed | 17,9 s | 3769 (3478) | 0,0187 | Solo «Observaciones visuales», con trazos, repasos y distribución. Sin interpretación, porque no se pidió, y sin diagnóstico. |
| A: retrato ilustrado | detailed | 14,9 s | 3515 (3102) | 0,0174 | Óvalo, frente, mejillas, barbilla, tono de piel según la luz, cabello, cejas, ojos e iris, lentes, nariz, boca, orejas y ropa. No atribuye identidad, etnia ni emociones. |
| A: seguimiento «arriba» | standard | 8,3 s | 1802 (1638) | 0,0111 | Responde sobre la zona superior. Mencionó «esta segunda imagen es un acercamiento», y ya se corrigió el prompt para que no hable de recortes. |
| D: página de libro | detailed | 14,0 s | 2982 (2725) | 0,0160 | Describe la estructura y lee el texto completo, palabra por palabra y en orden, incluido el número de página. |
| Gráfico de barras | standard | 7,7 s | 1729 (1593) | 0,0099 | Tipo, título, ejes y los cinco valores exactos, con subida, bajada y pico. |

- **Imágenes:** la entrada cuesta poco, alrededor de 2000 tokens por imagen. El razonamiento domina el gasto.
- **Proyección con el crédito de 150 USD:**
  - unas 14.000 respuestas `standard`;
  - unas 2.100 respuestas `deep` con imágenes de este tamaño.
- **Fotos reales:** pueden consumir más.

## Despliegue (lo hace Astra; no se tocó el VPS)

1. **Backend:**
   - Desplegar la rama tras revisar y fusionar #4 y #5, en ese orden.
   - Ejecutar `python manage.py migrate`. La migración nueva es `assistance.0001_initial`, que crea la tabla
     `assistance_metausage`.
   - No hay cambios de permisos ni de tratamiento de datos que se activen solos: todo sigue detrás de los mismos
     interruptores (`AINGEL_REAL_DATA`, `PRIVATE_OWN_MEDIA_TEST`, `META_ALLOWED_USER_IDS`, permisos por persona).
2. **Opcional:** `AINGEL_META_BUDGET_USD=150`. Hace que las llamadas se detengan al llegar al presupuesto.
   - Solo cuenta lo registrado desde el despliegue.
   - Sin la variable, solo se registra.
3. **Tiempos de espera:** `deep` puede tardar unos 60 s, y más con fotos grandes.
   - Daphne no tiene límite de lectura y Caddy no impone uno por defecto.
   - Si hay una CDN o un proxy con límite delante, debe permitir 180 s en `/api/v1/vision/`.
4. **Caché:** las sesiones viven en la caché por defecto, que en producción es el Redis efímero con TLS. No usan el
   Redis de cuotas.
5. **Clientes:** compilar la web y la APK nuevas. Los clientes anteriores siguen funcionando con `scene/`.

## Reversión

- **Código:** revertir el commit o desplegar la versión anterior. Los clientes nuevos con un backend viejo recibirán
  404 en `vision/` y mostrarán «No pude analizar la imagen».
- **Base de datos:** `python manage.py migrate assistance zero` elimina solo la tabla de consumo, que no tiene
  contenido personal. No hace falta hacerlo para revertir el código.
- **Sesiones en caché:** caducan solas en 15 minutos.

## Límites conocidos

- **Latencia:** `deep` tarda alrededor de un minuto y `detailed` alrededor de 15 s. Es el precio de no recortar la
  calidad.
- **Clasificación:** las palabras clave cubren español e inglés y fallan con formulaciones raras. Los campos
  explícitos siempre prevalecen.
- **Preguntas generales tras una respuesta visual:** en Android, una pregunta hecha justo después de una respuesta
  visual se trata como seguimiento de la imagen durante 15 minutos. Para cambiar de tema hay que borrar la
  conversación.
- **Inicio web:** el orbe de inicio no ofrece seguimientos; para eso está la pantalla «Ver».
- **Sin probar en el teléfono:** el flujo en el teléfono, con Meta real y fotos propias, no se probó. Hace falta el
  despliegue y la prueba privada del propietario.
- **Presupuesto:** el registro empieza vacío, así que lo gastado antes no cuenta. Los precios son los de lista
  publicados (`docs/META_MODELS.md`), no la factura.
- **Fuera del registro:** `captions` (Voice Transcribe) no registra consumo, porque no da tokens. `locate`
  (`sam-3.1`) registra tokens con coste 0, porque no hay un precio publicado verificado.

## Pendiente de AINGEL 3.0

- **Fase 2:** AINGEL Desktop para Windows.
- **Fase 3:** libros y PDF con OCR.
- **Fase 4:** subtítulos del audio del sistema (WASAPI).
- **Fase 5:** registro de señas validadas.
- **Fase 6:** instalador y sección de descarga.

Ninguna existe todavía. No se publicó ningún enlace de descarga.
