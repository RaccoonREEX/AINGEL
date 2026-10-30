# Conversación, visión y lengua de señas — 28 de octubre de 2026

Primera experiencia funcional de conversación por voz, «ojos» de AINGEL y traductor de lengua de señas,
en web y Android. Todo usa material de prueba sintético mientras se revisan las condiciones de uso de
datos reales con Meta.

## 1. Conversación general

**Qué hace.** Las preguntas sobre rutinas, mensajes, recuerdos o «Necesito apoyo» se siguen respondiendo
en AINGEL con los datos del perfil (no salen del servidor de AINGEL). Cualquier otra pregunta va a la
conversación general: `POST /api/v1/profiles/<id>/conversation/` → Meta Muse Spark (`muse-spark-1.3`).

**Conocimiento.** Antes de llamar al modelo, el servidor busca en el índice local de MedlinePlus
(2.028 resúmenes, `care.knowledge.best_topic`) un tema cuyo título aparezca en la pregunta (coincidencia de
palabras del título, sin búsqueda semántica: si no hay coincidencia clara no se adjunta nada). Si hay
coincidencia, se envía al modelo un extracto público (≤ 4.000 caracteres) y la respuesta muestra
«Generado por Meta Muse Spark con un resumen de MedlinePlus» con enlace al tema. Si no hay fuente, la
respuesta dice «sin fuente consultada» y las instrucciones obligan al modelo a reconocer que no tiene una
fuente fiable para preguntas de salud. **No se ha entrenado ningún modelo con MedlinePlus ni con datos
clínicos**: es una búsqueda de texto cuyo extracto se adjunta a la pregunta.

**Qué sale del equipo.** Desde el 29-10-2026, con las autorizaciones dadas al crear la cuenta (ver [Inicio y Ajustes](HOME_AND_SETTINGS.md#autorizaciones-al-crear-la-cuenta)); antes, solo con la casilla de modo de prueba.

| Se envía a Meta | No se envía |
|---|---|
| La pregunta actual y hasta 5 pares pregunta/respuesta anteriores *de la conversación general* | Nombre, nombre preferido, notas, alergias, contactos |
| Opciones categóricas: trato (formal/informal/neutral), longitud de frase, ritmo, un paso a la vez | Rutinas, mensajes, recuerdos, fotos del perfil |
| Extracto público de MedlinePlus, si coincide | Respuestas locales de rutinas, mensajes o recuerdos (no entran en el historial) |

El historial se guarda **solo en la memoria de la pantalla** (web: estado de React; Android: estado de
Compose). Se borra con «Borrar conversación», al salir de la conversación o al cerrar la app. El servidor
no lo guarda (`store: false` en la llamada y sin registro del contenido; la auditoría solo anota el evento
`companion.conversation`). El servidor rechaza la solicitud si falta `synthetic: true` o si
`AINGEL_SYNTHETIC_TESTS_ONLY` no es `1`. Límites: 12 turnos, 1.000 caracteres por turno, 8.000 en total,
12 solicitudes por minuto.

**Tono.** Instrucciones del sistema: tranquilo, respetuoso, cercano y paciente; sin infantilizar ni suponer
capacidades por un diagnóstico; no dice conocer datos privados; no diagnostica ni da dosis; ante peligro
inmediato remite a servicios de emergencia o a una persona de confianza sin inventar números.

**Sin conexión.** Si Meta no responde, AINGEL lo dice y ofrece las funciones locales (Hoy, mensajes). En
modo `mock` (sin clave) muestra «Modo de prueba» y, si hay tema de MedlinePlus, el extracto público sin modelo.

## 2. Escuchar y responder con voz

- Web: `useSpeechInput` (micrófono + `SpeechRecognition` del navegador). Android: `VoiceInput`
  (`SpeechRecognizer` del sistema). El permiso se pide al tocar el micrófono; la píldora «AINGEL está
  escuchando» y la nota «Micrófono activo. El audio no se guarda» se muestran mientras escucha y el
  micrófono se libera al terminar.
- **El reconocimiento de voz lo hace el servicio del navegador o del sistema** (en Chrome/Edge y en
  Android con Google suele ser un servicio en la nube del fabricante). AINGEL no guarda audio.
- Lectura: voces del navegador (`speechSynthesis`) y de Android (`TextToSpeech`). Interruptor «Leer
  respuestas en voz alta», botones «Repetir» y «Detener lectura». No hay voz clonada ni respuesta en
  tiempo real por streaming.
- Si no hay reconocimiento o lectura, se muestra el error y se puede seguir por texto.

## 3. Los ojos de AINGEL (pantalla 3a)

Botón de ojos en la barra superior (web y Android). Al activarlo se abre la cámara trasera y se ve solo a
través de los ojos del orb (web: `<video>` bajo el canvas con `destination-out`; Android: CameraX
`PreviewView` bajo el orb con `BlendMode.DstOut`). «Describir lo que ves» y «Buscar» capturan **un único
fotograma completo** en memoria y lo envían a `scene/` (Muse Spark) o `locate/` (SAM 3.1). Para enviar a
Meta hay que marcar «La imagen es de prueba (sin personas ni datos reales)…»; si no, el servidor lo rechaza.
No hay grabación continua ni vigilancia. Cada respuesta indica si viene de Meta o del modo de prueba y
advierte que no es una guía segura para moverse. El reconocimiento facial local existente no cambia.

## 4. Traductor de lengua de señas

Botón con una mano en la barra superior y en «Más». Quien signa es **AINGEL**: el orb con dos manos
articuladas en 3D (three.js 0.184.0; guante blanco de tres tonos, contorno azul marino, puño dorado) del
motor del paquete *AINGEL Manos y Señas v1.0.0* (`sign-language/engine` v0.1.1). En Android las mismas
manos se dibujan de forma nativa con OpenGL ES 3 (`Hands3D.kt`: misma geometría, mismo sombreado de tres
tonos y mismo contorno), sobre el orb nativo. Si no hay WebGL u OpenGL ES 3, signa el motor 2D del mismo
paquete (`AingelSigner`). No hay vídeo de ninguna persona.

Pantalla limpia: el orb con las manos, el estado, las señas en curso (con repetir y velocidad 1,5× por defecto / 1× / 0,75× /
0,5×; con «ritmo lento» en Personalizar, la web empieza en 1×) y, debajo, un botón **«Traducir»** con los ojos de AINGEL que despliega hacia abajo los cuatro
modos (con iconos, se usan sin leer):

| Modo | Qué funciona de verdad |
|---|---|
| Voz a señas | Micrófono → reconocimiento de voz → regla de frase del catálogo → AINGEL signa la secuencia y se resalta la seña en curso. |
| Texto a señas | Frase escrita (o un ejemplo del catálogo) → misma regla → AINGEL la signa. |
| Señas a voz | Cámara frontal a través de los ojos (opcional). **No hay reconocimiento automático**: la persona toca las señas de su mensaje en un tablero de 20 pictogramas; AINGEL puede signarlo de vuelta («Ver mi mensaje en señas») y lo dice en voz alta. |
| Señas a texto | Igual, y el texto aparece en un campo editable para corregirlo; «Mostrar en grande» lo enseña a pantalla completa. |

**Vocabulario (comprobado):** alfabeto manual de una mano (27 letras, J y Z con trazo, Ñ con ondulación),
números 0–10 y 43 palabras y acciones (yo, tú, hola, gracias, por favor, sí, no, bien, mal, agua, comida,
medicina, casa, parque, pelota, libro, baño, doctor, familia, mamá, papá, hija, hijo, dolor, ayuda, hoy,
mañana, ayer, pregunta; caminar, leer, comer, beber, dormir, esperar, ir, venir, llamar, ayudar,
necesitar, querer, tener, jugar). El paquete las declara **diseño AINGEL pendiente de validación por
personas sordas señantes de LSEC**, no una fuente lingüística verificada; la pantalla lo indica siempre
(«Diseño AINGEL · pendiente de validar en LSEC»).

**Regla de frase (la del catálogo, no la gramática de LSEC):** conjugaciones y sinónimos llevan a su seña
(quiero → querer, voy → ir, médico → doctor, hambre → comer, «por favor», «me llamo X», números); el
tiempo (hoy, ayer, mañana) va al inicio y la marca de pregunta al final; lo que no tiene seña se deletrea;
artículos y enlaces se omiten. La pantalla muestra cómo entendió la frase: azul = seña, dorado =
deletreo, tachado = omitido. El orb cambia de expresión con algunas señas (contento con «hola»,
«gracias»…; duda con «pregunta») y se pone contento al terminar.

**Por qué no hay traducción libre ni reconocimiento.** No existe hoy un modelo de reconocimiento de LSEC
ni un traductor texto→LSEC con derechos compatibles para un producto. El corpus ecuatoriano (17,8 GB) es
un punto de partida para entrenar y evaluar, pero no trae un modelo; el artículo con vocales LSEC es solo
no comercial (CC BY-NC-SA); el diccionario Gabriel Román tiene copyright. Los clips de vídeo del corpus
se probaron y se retiraron: la persona del vídeo no es AINGEL y el producto debe mostrar a AINGEL.

**Módulos.** Captura autorizada (`useCamera` / `LiveCamera`, `useSpeechInput` / `VoiceInput`) →
transcripción (servicio del navegador/sistema) → interpretación (`buildSentence` en `signLexicon.ts` /
`SignLexicon.kt`, local, sin red) → secuencia de identificadores de seña → reproducción en 3D
(`AingelHands3D`: `hands3d/` en web, cargado solo al abrir el traductor; en Android `AingelHands3D.kt` /
`Hands3D.kt` con `assets/hands3d/signs3d.json`, exportado desde la web con `npm run export:android-hands`,
así web y Android signan exactamente los mismos datos). Respaldo 2D: `AingelSigner`.

**Cómo pasan las señas al 3D (sin rediseñarlas).** El catálogo 2D (`signData.ts`: 81 señas —27 letras, 11 números, 29 palabras y 14 acciones—; las 20 frases del catálogo son secuencias de ellas) es la
única fuente. `hands3d/convert.ts` convierte cada forma de mano en ángulos del esqueleto pasando la
geometría 2D por el propio `landmarksToPose()` del paquete (pulgar incluido), y cada keyframe en
posición de muñeca, rotación (yaw/pitch/roll con el eje y invertido) y escala por mano. Comprobación
numérica sobre todos los keyframes de las 81 señas: diferencia media entre 2D y 3D de 0,02–0,09 radios
del orb en puntas de dedos y muñeca; la mayor, 0,26, siempre en la punta del pulgar (proporciones
distintas). Cambios al motor del paquete, marcados «AINGEL»: escala por mano y biblioteca en memoria
(sin `fetch` a `/data`). En Android se probó primero el motor web dentro de un WebView, pero en el
Galaxy Z Flip 4 el WebView no se componía dentro de la pantalla Compose (dibujaba a 60 fps, pero sin
mostrarse); por eso se portó el motor a OpenGL nativo.

**No integrado del paquete:** los 6 movimientos de prueba del motor 3D (el propio paquete dice que «no
son señas») ni la captura con MediaPipe (preparada, sin conectar). Los vídeos LSEC del paquete de recursos
muestran a una persona y no se usan; el artículo con
vocales LSEC es solo no comercial. Los alfabetos de otros países (paquete internacional) son material de
referencia con licencias distintas (algunas CC BY-SA) y no se incorporan a la app.

**Backend.** `care.signs` (`signs/catalog/`, `signs/lookup/`, `signs/clips/<id>/`) se conserva para un
futuro catálogo de señas revisadas por personas sordas (hash SHA-256, atribución, estado
`reviewed` | `corpus_annotation`), pero el catálogo local está **vacío** y las apps no lo consultan. Para
un futuro avatar validado se propone que cada elemento de la secuencia sea
`{"type": "avatar", "gloss": [...], "nmm": [...], "timing_ms": [...]}` (glosas y rasgos no manuales).

**Para llegar a interpretación libre faltaría:** (1) acordar con personas sordas de Ecuador y FENASEC la
lista de señas y frases y su variación regional; (2) validar o rehacer las animaciones de AINGEL con
ellas; (3) entrenar y evaluar un reconocedor (p. ej. puntos de mano con MediaPipe, Apache-2.0, sobre el
corpus LSEC CC BY 4.0) con signantes separados entre entrenamiento y prueba; (4) un traductor con
gramática LSEC y rasgos no manuales; (5) evaluación de comprensión con participantes sordos.

## 5. Servicios externos que reciben datos

| Servicio | Qué recibe | Cuándo |
|---|---|---|
| Meta Muse Spark (`api.meta.ai`) | Preguntas de la conversación, opciones de trato, extracto de MedlinePlus, apoyos indicados y alergias; con búsqueda web cuando la pregunta lo necesita | Con la autorización «Enviar datos a Meta» dada al crear la cuenta |
| Meta Muse Spark | Un fotograma | «Describir lo que ves» / «Ver y describir», con las autorizaciones de cámara y Meta |
| Meta Muse Spark | Un fotograma cuando la escena cambia, como máximo uno cada 4 s (cámara trasera) | «Vigilancia continua» (5a), con las autorizaciones de cámara y Meta |
| Meta Muse Spark | La frase que se va a signar (escrita o reconocida por voz) y el vocabulario de señas de AINGEL | Traductor de señas, «Escuchar y traducir» y «Escribir y traducir», con la autorización «Enviar datos a Meta»; sin ella, regla local |
| Meta SAM 3.1 | Un fotograma y el nombre del objeto | «Buscar», con las autorizaciones de cámara y Meta |
| Meta Voice (`muse-voice-transcribe`) | Audio | Solo en «Escuchar» (subtítulos), sin cambios |
| Reconocimiento de voz del navegador / Android | Audio del micrófono | Al tocar el micrófono (Inicio y Voz → señas) |
| Google Fonts | Petición de la fuente | Web, al cargar la página |

La lectura en voz alta (síntesis), el reconocimiento facial y la animación de señas son locales.

## 6. Pruebas realizadas

- Backend: 47 pruebas en `assistance` y `care.test_signs` (conversación: alcance, consentimiento, límites,
  que no se envían datos del perfil, MedlinePlus, modo de prueba, fallos; señas: esquema del catálogo,
  catálogo por lengua). Regla de frase y vocabulario: `SignLexiconTest` (Android, JVM).
- Web (navegador del escritorio, 1280×800 y 360×788): sin casilla no se envía nada; con casilla, dos
  llamadas sintéticas reales a Muse Spark: «¿Qué es la diabetes?» (respondió con trato de usted, frases
  cortas y fuente MedlinePlus) y una pregunta de seguimiento (usó el contexto, «sin fuente consultada»).
  Traductor: «Hola, necesito agua y medicina» → AINGEL signa Hola · Agua · Medicina con las manos
  flotantes y la etiqueta de animación ilustrativa.
- Android, en Samsung Galaxy Z Flip 4 (Android 16, fuente 1,15): conversación con casilla de prueba y una
  llamada sintética real («¿Qué es el asma?» → respuesta corta con fuente MedlinePlus «Asma», leída en voz
  alta con el orb en «respondiendo»); ojos: permiso de cámara «Solo esta vez», cámara trasera visible solo
  por los ojos, captura de un fotograma rechazada por el servidor al no marcar la casilla de imagen (no se
  envió nada a Meta; no se enviaron imágenes reales); cámara liberada al cerrar (sin clientes activos).
  Traductor: frase escrita «Hola que tal quieres agua» → AINGEL signa Hola y Agua con las manos
  flotantes; «Señas a texto»: tablero de pictogramas → texto editable y «Ver mi mensaje en señas»
  (AINGEL lo signa de vuelta); «Señas a voz» con cámara frontal por los ojos y liberación al cerrar.
- No probado en el teléfono: voz → señas con el micrófono (requiere hablar cerca del teléfono; el paso
  texto → señas se comprobó escribiendo) y el análisis de imagen con Meta (se evitó enviar imágenes reales).
- No probado aún: cámara y micrófono reales en el navegador del panel de pruebas (bloqueados allí).
