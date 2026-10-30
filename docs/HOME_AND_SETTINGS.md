# Inicio con menú (5a) y Ajustes de sonido y voz (5b) · app Android

Paquete de diseño: *AINGEL Inicio y Ajustes v1.0.0* (29-10-2026). Solo para la app móvil de la persona cuidada.
Probado en Samsung Galaxy Z Flip 4 (Android 16, fuente 1,15).

## 5a · Inicio con AINGEL al centro

Botón arriba a la derecha que se despliega hacia abajo en la misma pantalla (con escalonado y velo blanco
desde la derecha; el saludo se oculta mientras está abierto). El botón se desplaza con la pantalla, así nunca
tapa el contenido. Las opciones salen de lo marcado al crear la cuenta (2c/2d): `hearing_assistance` →
**Traducir con manos**; `visual_assistance` → **Ver con AINGEL**; con las dos marcadas salen las cinco
opciones; sin ninguna, el inicio conserva los botones anteriores (mano y ojos).

| Opción | Qué hace de verdad |
|---|---|
| Escuchar y traducir | Reconocimiento de voz del sistema → regla de frase del catálogo → manos 3D alrededor del orb. Vuelve a escuchar sola después de cada frase, hasta «Terminar». Probado en el teléfono con voz real. |
| Ver y traducir | Primero muestra dos salidas: altavoz (decir en voz alta) o «Aa» (texto grande). Abre la cámara frontal solo a través de los ojos del orb. **No hay reconocimiento de señas**: la persona toca en un tablero las señas que hace y AINGEL las dice o las muestra en grande. No se inventan frases. |
| Escribir y traducir | Saluda con «hola» y signa lo que se escriba (regla de frase del catálogo). |
| Ver y describir | Cámara trasera por los ojos; a 1,2 s describe una vez en voz alta con la advertencia «No uses esta respuesta como guía segura para moverte». Sin las autorizaciones de la cuenta, el servidor no envía la imagen y AINGEL dice dónde activarlas. |
| Vigilancia continua | Ver abajo. |

Tarjeta **Siguiente**: si la rutina la organiza otra persona, tocarla solo muestra 3 s «Este recordatorio lo
organiza Lucía. Pídele a Lucía que lo cambie si lo necesitas.» (nombre real de quien la creó: campo nuevo
`author_name` en `RoutineSerializer`). Las rutinas propias siguen abriendo «Hoy».

### Vigilancia continua (perfil de ceguera)

`WatchService`: servicio en primer plano de tipo `camera`.
- **Notificación fija:** «AINGEL · Vigilancia continua», con la última descripción, la salida de audio y
  «Detener».
- **Funcionamiento:** CameraX sin vista previa, `WakeLock` parcial.
  - El teléfono mira la cámara en vivo: unas 3 veces por segundo reduce la imagen a una cuadrícula de brillo de
    16×12 (`WatchChange.kt`). Esto no tiene costo y no sale del teléfono.
  - Solo cuando la escena cambia respecto de la última descrita, envía un fotograma a `scene/`. Por ejemplo, cuando
    entra alguien, cambia la luz o se gira el teléfono.
  - Como máximo envía uno cada 4 s y nunca mientras AINGEL está hablando. Si la escena no cambia, se queda en
    silencio.
  - Si falla, espera 6 s más antes de reintentar. Dice el resultado por la salida elegida en Ajustes.
  - Los cambios generales de exposición se compensan. Un teléfono en la mano que se mueve todo el tiempo cuenta
    como escena nueva, así que describe cada 4 s más el tiempo de hablar.
- **Al empezar:** la app pasa a segundo plano.
- **Burbuja flotante:** aparece solo si la persona concede «Mostrar sobre otras apps» desde el enlace del panel.
  AINGEL nunca cambia ese permiso por sí mismo. Tocar la burbuja vuelve a la app.
- **Con el teléfono bloqueado:** sigue describiendo. Comprobado: 3 capturas en 22 s con la pantalla apagada;
  el indicador de cámara del sistema marca el uso.
- **Detener:** «Detener», en la notificación o en la tarjeta del inicio, libera la cámara (comprobado:
  `CAMERA_STATE_CLOSED`).
- **Privacidad:** igual que «Ver y describir». La imagen va al servidor de AINGEL, que solo la reenvía a Meta con
  las autorizaciones de cámara y Meta de la cuenta, y no la guarda. En modo de prueba no se analiza nada y
  AINGEL lo dice una sola vez. Si el servidor pide el consentimiento, el servicio se detiene y lo explica.
- **No implementado:** la orden de voz «Hola AINGEL, detente» (tampoco lo estaba en la maqueta). Por eso la app
  no la anuncia.

## 5b · Ajustes de sonido y voz (Más → «Ajustes de sonido y voz»)

- **Voz de AINGEL.** Lista los dispositivos reales conectados: altavoz del teléfono y cualquier auricular
  Bluetooth o con cable. Se actualizan al conectar o desconectar.
  - **Cómo se enruta:** el TTS del sistema suena en el proceso del motor y no deja elegir salida. Cuando hay que
    respetar una elección, la frase se sintetiza a un archivo privado en caché y se reproduce con
    `MediaPlayer.setPreferredDevice` (`AingelVoice.kt`). «Altavoz del teléfono» fuerza el altavoz solo si hay
    otra salida conectada.
  - **Dónde se usa:** la app y la vigilancia usan la misma voz. «Probar sonido» dice una frase de prueba.
- **Micrófono.** Lista el del teléfono y los de auriculares. Android decide qué micrófono usa el dictado: AINGEL
  pide el elegido como dispositivo de comunicación mientras escucha (Android 12+). Con algunos auriculares el
  sistema puede seguir usando el del teléfono, y la pantalla lo dice.
- **Control por voz.**
  - **Al activarlo la primera vez:** AINGEL se agranda, pone las manos 3D junto a los oídos (gesto de interfaz
    `listen_ear` del paquete, no una seña) y pide repetir «Hola AINGEL» (o «AINGEL») tres veces después de
    él, con tres puntos dorados.
  - **Mientras se usa:** con el inicio abierto y en reposo, AINGEL escucha la frase y después la pregunta.
  - **Texto corregido para no prometer lo que no hace:** «Ya conozco tu frase» en lugar de «Ya reconozco tu
    voz». No hay verificación de hablante: la pantalla dice «AINGEL reconoce la frase, no tu voz».
  - **Límites:** no escucha en segundo plano ni con la pantalla bloqueada. Para eso haría falta un motor de
    palabra de activación en el dispositivo (p. ej. openWakeWord, Apache-2.0), aún no integrado.
- **Dónde se guarda:** solo en el teléfono (`SharedPreferences` `aingel-audio` y `aingel-voice`).

## Archivos

`HomeModes.kt` (menú, tablero, tarjeta Siguiente), `HomeScreen.kt` (modos), `WatchService.kt`, `AudioRoute.kt`,
`AingelVoice.kt`, `SoundSettings.kt`, `VoiceInput.kt` (micrófono elegido). El gesto `listen_ear` está en
`web/src/components/aingel/hands3d/listen_ear.json` y se exporta a `assets/hands3d/signs3d.json` con
`npm run export:android-hands`. Pruebas: `HomeModesTest` (menú según perfil, detección de la frase),
`test_routine_shows_who_organizes_it` (backend).

## Autorizaciones al crear la cuenta

Desde el 29-10-2026 (decisión del responsable del proyecto) las apps **no preguntan nada** por uso: ni casillas
de «modo de prueba» ni de «imagen de prueba». Las autorizaciones se dan una vez, en el paso «Activar» del registro
web, y se cambian en Personalizar → Autorizaciones:

| Autorización | Cubre |
|---|---|
| Cámara: ver por la persona | Describir, buscar objetos, vigilancia continua |
| Micrófono: escuchar | Conversar, traducir a señas, subtítulos, «Hola AINGEL» |
| Enviar datos a Meta para responder | Preguntas, imágenes y audio que haya que analizar, apoyos indicados y alergias (recomendaciones adaptadas); búsqueda web cuando haga falta |

- **Dónde se guardan:** en `Profile.consents` (versión, fecha y quién autorizó, `care/consent.py`). El servidor
  las comprueba en cada envío: conversación, imagen (`scene/` y `locate/` con el campo `profile`), subtítulos
  (mensaje `start` con `profile`) y chat de pruebas.
- **Interruptor del servidor:** solo se envían datos reales si además está activo `AINGEL_REAL_DATA=1`.
  `scripts/serve_local.py` lo activa cuando arranca en modo Meta con la clave. Sin autorización, AINGEL dice dónde
  activarla y sigue resolviendo lo local (rutinas, mensajes, recuerdos).
- **Pruebas sintéticas:** la declaración `synthetic` sigue funcionando (imagen de formas incluida, scripts de
  prueba).
- **Fuera de este cambio:** el consentimiento del reconocimiento facial de familiares se mantiene aparte, porque
  lo da cada familiar sobre su propio rostro.

## Conversación continua y búsqueda web

- **Conversación continua.** Una conversación empezada por voz (micrófono o «Hola AINGEL») es continua:
  - Cuando AINGEL termina de responder, vuelve a escuchar solo.
  - Cada turno tiene una ventana de 25 s. El reconocedor de Android se corta tras unos segundos de silencio y se
    reinicia sin aviso dentro de la ventana.
  - Si pasan 25 s sin que nadie hable, AINGEL deja de escuchar y **no responde nada**.
  - Escribir, tocar para detener o borrar la conversación termina el modo continuo.
- **Respuestas personalizadas.** Con la autorización de Meta, la conversación incluye los «Apoyos indicados» del
  registro y las alergias. Nunca incluye nombres, otras notas, rutinas, mensajes ni recuerdos.
- **Búsqueda web.** Se ofrece la herramienta `web_search` de Meta. El modelo la usa solo si la pregunta necesita
  información actual, lugares, servicios o recomendaciones que MedlinePlus no cubre.
- **Qué se muestra.** Las páginas citadas (`url_citation`, solo `https://`) aparecen bajo la respuesta. Los
  mensajes intermedios de la búsqueda («Busco…», `phase: commentary`) se descartan.
- **Prueba real (29-10-2026):** «¿Qué actividades accesibles me recomiendas en Quito este fin de semana?» → 2
  búsquedas, respuesta adaptada (Mitad del Mundo, Casa del Alabado con rampas y ascensor).

## AINGEL usa las funciones de la app

Antes, Meta contestaba «No tengo acceso a su cámara» cuando la persona pedía que mirara. Ahora el modelo sabe que es
la voz de la app y puede pedirle al teléfono que haga cosas.

- **Primero, en el teléfono.** `cameraCommandOf` (`Today.kt`) reconoce sin conexión las peticiones de cámara:
  - «¿Qué ves?», «mira por la cámara», «lo que yo no puedo ver» → describe con la cámara trasera.
  - «activa la vista continua», «vigila» → empieza la vigilancia continua.
  - «detén la vigilancia», «apaga la cámara» → la detiene.

  Estas peticiones no pasan por Meta.
- **Si no, Meta decide.** El teléfono envía en `actions` las funciones que sabe hacer:
  - `describe_surroundings`
  - `find_object(object_name)`
  - `start_continuous_watch`, `stop_continuous_watch`
  - `listen_and_sign`
  - `open_sign_translator`

  El backend (`assistance/conversation.py`) las ofrece a Meta como herramientas (`APP_ACTIONS`) y le explica la app
  (`app_context`). Cuando Meta llama a una, la respuesta trae `action` y el teléfono la ejecuta en lugar de leer un
  texto.
- **Límites.** Solo pasan funciones de la lista y con argumentos seguros (`valid_action`: nombre de objeto de hasta
  80 caracteres, sin `< > |` ni saltos de línea). Las imágenes siguen sujetas a la autorización de cámara y Meta del
  registro.
- **Sin funciones.** Si un cliente (la web) no envía `actions`, el modelo igual sabe qué hace la app y explica la
  frase o el menú que hay que usar.
- **Prueba en el Flip 4 (29-10-2026):**
  - «qué ves» → descripción real de la cámara.
  - «busca mis llaves por favor» → Meta llamó a `find_object`, SAM 3.1 analizó la foto («No encontré llaves»).
  - «activa la vista continua» → servicio activo, una captura cada 7–10 s.
  - «detén la vigilancia» → «Detuve la vigilancia continua.» y no hubo más capturas.
- Las respuestas de imagen dicen «imagen de la cámara, no guardada». Las de conversación con búsqueda dicen «con
  búsqueda web» aunque Meta no devuelva enlaces.

## Reconocer a la familia al mirar

- **Cuándo.** Al describir («qué ves», «Ver y describir») y en la vigilancia continua, el teléfono envía
  `family=true` a `scene/`.
- **Qué dice.** Si un familiar inscrito está delante, AINGEL dice primero quién parece ser («Parece ser tu hijo
  David.») y Meta describe su ropa y qué hace.
- **Límites.**
  - Solo para la persona dueña del perfil, con «Reconocer familiares» activado (contraseña y consentimiento).
  - Solo reconoce a familiares que inscribieron su propia foto con su consentimiento (`care/faces.py`).
  - La comparación se hace en nuestro servidor con OpenCV (YuNet + SFace). Meta nunca recibe el nombre ni la plantilla
    facial: solo se le pide describir a «una persona que el usuario conoce».
  - Es una coincidencia posible, no una identidad verificada; por eso dice «parece ser».
- **Vigilancia continua.** El nombre no se repite en cada captura: se vuelve a decir pasados 3 minutos.
- **Prueba (29-10-2026):**
  - David inscrito como «Hijo» en la cuenta de demostración, con 1 foto.
  - `scene/` con esa foto → «Parece ser tu hijo David.» y «lleva gafas y una chompa verde oscura».
  - Con 2–3 fotos (de frente, con distinta luz) el reconocimiento por la cámara es más fiable.
  - En vivo, con la vigilancia por cambios, el reconocimiento corrió en cada captura y no reconoció a David. Era una
    selfie frente al espejo, con el teléfono delante; Meta describió «lentes y un buzo oscuro con cuello rojo».
    Con una sola foto pequeña (189×204) no alcanza: hay que inscribir 2–3 fotos de frente.
  - Reinscrito con 3 fotos de frente:
    - Similitud entre las dos fotos buenas: 0,68. La foto pequeña quedaba en 0,50–0,52.
    - Una cuarta foto en blanco y negro con la cabeza inclinada no pasó el detector (confianza 0,90 justo en el
      umbral), así que no se inscribió.
    - Comparada aparte contra la inscripción, esa foto coincidió con 0,58 (umbral 0,55).
  - En vivo con la cámara trasera del Flip 4, «qué ves» → «Parece ser tu hijo David. La persona al frente lleva gafas
    y un suéter azul oscuro con cuello rojo, y parece estar posando con las manos en la cintura…».
- **Vigilancia por cambios (29-10-2026):**
  - Con la escena quieta envió 2 fotos en 45 s; antes, cada 7 s, habrían sido unas 6.
  - La segunda foto salió cuando apareció una persona delante.

## Velocidad de las manos y micrófono ocupado (29-10-2026)

- **Velocidad.** Las manos de AINGEL van a 1,5× por defecto en todas las pantallas (`HANDS_SPEED` en
  `AingelHands3D.kt` y `signData.ts`). En el traductor, el botón de velocidad recorre 1,5× → 1× → 0,75× → 0,5×.
- **Micrófono ocupado.**
  - Problema: al abrir «Escuchar y traducir», o el micrófono del traductor, justo después del inicio, aparecía
    «No pude reconocer la voz en este teléfono».
  - Causa: el oyente de «Hola AINGEL» seguía con el micrófono abierto y Android respondía «ocupado».
  - Arreglo, primera parte: el oyente se detiene al abrir el menú, un modo u otra pantalla.
  - Arreglo, segunda parte: los errores pasajeros (`transientRecognizerError`) se reintentan hasta 3 veces antes de
    avisar.
  - Comprobado en el Flip 4: tras 5 s en el inicio, «Escuchar y traducir» queda en «AINGEL está escuchando».
- **«¿Cómo estás?» se signaba «comer».**
  - Causa: el léxico quita las tildes, así que «cómo» (pregunta) quedaba igual que «como» (de comer).
  - Ahora `buildSentence` reconoce «cómo estás» y sus variantes y las signa TÚ BIEN ?. Las variantes son «cómo
    está», «cómo te va», «cómo te sientes», «cómo has estado» y «how are you».
  - Con sujeto, «¿cómo está tu mamá?» → TÚ MAMÁ BIEN ?.
  - «Cómo» con tilde, o al empezar una pregunta, es la palabra interrogativa y no lleva seña.
  - Mismo cambio en Android (`SignLexicon.kt`) y en la web (`signLexicon.ts`). Comprobado en el Flip 4.

## Signar por el sentido de la frase (29-10-2026)

- **Qué cambia.** Antes de signar, la frase va a Meta (`POST profiles/<id>/signs/gloss/`, `assistance/gloss.py`).
  Meta elige las señas por el sentido, no palabra por palabra.
  - Se usa en el traductor, en «Escuchar y traducir» y en «Escribir y traducir»; en la web, en el traductor.
  - El cliente envía su vocabulario: las 43 palabras y los números, con sus nombres.
  - Meta responde llamando a `sign_sequence` con ids del vocabulario o `spell:<palabra>` para nombres.
  - El servidor rechaza la respuesta entera si trae una seña inventada.
- **Respaldo.** Si no hay Meta, se usa la regla local (`buildSentence`), como antes. Pasa en modo de prueba, sin la
  autorización «Enviar datos a Meta», sin conexión, si Meta tarda más de 6 s o si la respuesta no sirve.
- **Caché.** Cada cliente guarda las últimas 64 frases, para no repetir la llamada.
- **Honestidad.** Debajo de las señas se muestra «Señas elegidas por el sentido de la frase (Meta), con el
  vocabulario de AINGEL.».
  - El modelo sabe que las señas son un diseño de AINGEL pendiente de validar en LSEC y que el orden es una regla
    simple, no gramática LSEC.
  - No se guarda la frase ni las señas; la auditoría solo anota `signs.gloss`.
- **Prueba con Meta (muse-spark-1.3, 1,1–3,2 s):**

  | Frase | Señas |
  |---|---|
  | «¿Cómo estás?» | TÚ BIEN ? |
  | «¿Qué tal te fue hoy?» | HOY TÚ BIEN ? |
  | «Tengo mucha hambre» | YO COMER |
  | «Mañana a las 3 viene el doctor» | MAÑANA 3 DOCTOR VENIR |
  | «Me llamo David y soy tu hijo» | YO D-A-V-I-D TÚ HIJO |
  | «Hola mamá, te traje agua» | HOLA MAMÁ YO VENIR AGUA |

  - Con un límite de 300 tokens Meta devolvió una respuesta incompleta; se subió a 600.
  - En el Flip 4, «que tal te fue hoy» se signó HOY TÚ BIEN ? con la nota de Meta.

## «Escuchar y traducir»: micrófono en pausa mientras signa (29-10-2026)

- **Problema.** El micrófono seguía activo y una frase nueva cortaba a las manos a la mitad.
- **Bloqueo.**
  - Al empezar a signar, `sign()` apaga el micrófono y cancela cualquier reinicio pendiente.
  - `hearListen()` no arranca mientras `signing` sea verdadero.
  - Se vuelve a escuchar 0,6 s después de que las manos avisan el final de la frase (`onSign(-1)`).
- **Respaldo.** Si ese aviso no llega (pantalla apagada, vista sin dibujar), un temporizador reabre el micrófono:
  4 s + 1,6 s por seña ÷ 1,5.
- **En pantalla.** Mientras signa se lee «AINGEL lo dice en señas · micrófono en pausa».

## Icono de la APK (AINGEL_Logo_APK v1.0.0, 29-10-2026)

- **Diseño.** Icono adaptativo con el orbe (cara azul marino, ojos blancos), arco azul a la izquierda y dorado a la
  derecha, sobre blanco.
- **Archivos.** Capa monocroma para los iconos temáticos (Android 13+) y versiones antiguas `mipmap-{mdpi…xxxhdpi}`.
  - `AndroidManifest.xml` usa `@mipmap/ic_launcher` y `@mipmap/ic_launcher_round`.
  - `ic_aingel` sigue como icono de la notificación y de la burbuja de vigilancia, que deben ser una silueta.
- **Pendiente.** El icono de 512 px para Google Play está en el paquete y no se publica desde aquí.

## Plegables y pantallas exteriores (AINGEL_Plegables v1.0.0, 29-10-2026)

`Foldables.kt`: `windowShape()` decide la forma de la ventana.

- **Pantalla exterior (6a–6c)** (`COVER`). Pantalla secundaria, o ventana pequeña (lado corto < 400 dp y largo < 640 dp).
  - Solo AINGEL: orbe en tono oscuro (`AingelOrb(dark = true)`: cara blanca, ojos azul marino, puntos claros, arco
    celeste) sobre negro puro.
  - Ocupa el 60 % del lado corto dentro de la zona segura. No hay texto, manos ni barra inferior.
  - Tocar → escucha; responde siempre en voz alta. TalkBack lee el estado.
  - Si se le pide mirar, explica que hay que abrir el teléfono: esa cámara apunta a la persona.
- **Dos paneles (6d–6e)** (`TWO_PANE`). Ventana de 600 dp o más de ancho: interior del Fold, pantalla doble, móvil en
  horizontal.
  - Izquierda: AINGEL y las manos. Derecha: saludo, opciones de «Traducir con manos» en lista y controles.
  - Los paneles miden lo mismo y el hueco de 32 dp cae sobre el pliegue o la bisagra, así que nada lo cruza.
- **Continuidad.** `configChanges` (tamaño, orientación) evita recrear la Activity al girar o cambiar de tamaño.
  Así no se pierden la conversación, el modo ni la escucha.
- **Límite del Flip 4.** La pantalla exterior de 1,9″ no abre apps de terceros por sí sola: hace falta Good Lock
  (MultiStar) o un lanzador para la pantalla exterior.
  - El Flip 5/6 y los razr sí permiten apps en la pantalla exterior.
  - No se usa `showWhenLocked`: con el teléfono bloqueado AINGEL podría decir datos privados a cualquiera.
- **Comprobado en el Flip 4** simulando tamaños con `adb shell wm size` (y restaurado):
  - 540×1050 px → pantalla exterior; al tocar escucha.
  - 2016×2340 px → dos paneles como 6d.
  - Tamaño normal → diseño de móvil.

## Auditoría de conexiones (29-10-2026)

Tres revisiones independientes: contratos de la API, Android y web. Todo lo corregido tiene pruebas o se comprobó en
el teléfono.

**Servidor**
- Solo la persona dueña del perfil cambia las autorizaciones (`consents_owner_only`, 403). La web las muestra como
  solo lectura a quien cuida.
- El chat de compañía funciona con la autorización del registro fuera del modo de prueba. Antes devolvía 503.
- Una acción no válida sin texto ya no da una respuesta vacía (`companion_empty_response`).
- Límite de `scene/` subido a 20/min, porque la vigilancia puede enviar hasta 15.

**Android**
- **Micrófono**
  - Las sesiones llevan número (`VoiceInput.start` devuelve un id, `stopIf`). El oyente de «Hola AINGEL» ya no
    apaga la escucha que se acaba de abrir con el micrófono.
  - No escucha en segundo plano: al ocultar la app (Inicio, bloqueo, cerrar la tapa) se libera el micrófono.
    «Escuchar y traducir» vuelve a escuchar al volver. Comprobado: sin sesiones de reconocimiento tras pulsar Inicio.
  - «Toca para terminar» sin haber dicho nada termina la conversación continua.
  - Un error ya no deja la escucha encendida.
- **Cámara**
  - Cada cámara libera solo lo suyo, ya no `unbindAll()`. La vigilancia se pausa mientras la app usa la cámara y
    sigue después.
  - `WatchService.stop` solo actúa si está activa. «Apaga la cámara» apaga los ojos.
- **Preguntas**
  - Las reglas locales solo cubren sus intenciones. «¿Qué debo hacer si me duele el pecho?» y «¿Dónde queda el
    hospital?» van a Meta.
  - Las órdenes de cámara son frases completas.
- **Datos y autorizaciones**
  - El historial se recorta a 8000 caracteres.
  - «Ver y describir» dice el nombre del familiar.
  - El registro en Android pide las tres autorizaciones, desactivadas hasta que la persona las conceda.
- **Pantalla**
  - El traductor de señas vuelve a donde se abrió.
  - La barra inferior no parpadea en «Escuchar y traducir».
  - «Escribir y traducir» muestra que está signando.
- **Señas.** «Como arroz» → YO COMER A-R-R-O-Z, sin pregunta, igual que en la web.

**Web**
- **Medios.** Cámara y micrófono ya no quedan encendidos si se sale con el permiso pendiente (contador de
  generación).
- **Respuestas**
  - Home no lee respuestas tras cancelar.
  - Reglas locales acotadas.
  - Envía `actions` y ejecuta describir, buscar y abrir el traductor.
  - Historial ≤ 8000 caracteres.
- **Mensajes de error.** Texto correcto para 404 y para `privacy_review_required`.
- **Traductor de señas.** Ritmo lento a 1× y sin glosas viejas tras cambiar de modo.
- **Textos.** Se quitaron restos de «sintético» y «cada 7 segundos».
- **`See`.** Ya no marca como sintética una foto por su nombre de archivo.

**Aviso de Meta.** Mientras la cuenta use créditos gratuitos, Meta advierte que puede usar el contenido para mejorar
sus productos (`docs/META_MODELS.md`). Ahora se dice en la autorización «Enviar datos a Meta» de la web y de Android, y
en el aviso de subtítulos.

**Sin cambiar a propósito**
- Rutas que ningún cliente usa: `signs/catalog/`, `GET profiles/<id>/`, `audit/`.
- Claves i18n y cadenas antiguas sin uso.
- `listen_ear.json` de la web: lo usa el exportador de manos.

## AINGEL en la pantalla exterior durante la vigilancia continua (Flip 4, 29-10-2026)

- **Problema.** Al cerrar el teléfono con la vigilancia activa no aparecía nada: Samsung no abre apps de terceros
  en la pantalla exterior.
- **Cómo se ve.** `WatchCoverActivity` aparece en la pantalla exterior (display 1, 512×260) sobre el bloqueo
  (`showWhenLocked`, `turnScreenOn`).
  - Solo el orbe oscuro sobre negro (6b): sin texto ni datos personales, así que no expone nada con el teléfono
    bloqueado.
  - El orbe «piensa» mientras se describe una foto y «habla» mientras AINGEL lee la descripción
    (`WatchState.looking` / `speaking`).
  - Tocarlo repite la última descripción. TalkBack lee la última descripción.
- **Cuándo.** `WatchService` escucha los cambios de pantalla (`DisplayManager.DisplayListener`). Cuando la principal
  se apaga y otra sigue encendida (teléfono cerrado), abre esa vista en esa pantalla.
- **Cuándo se cierra.** Al abrir el teléfono o apagar la pantalla (`onStop`), o cuando termina la vigilancia.
- **Requisito.** Android solo deja que un servicio en segundo plano abra una pantalla si la app tiene «Mostrar sobre
  otras apps», el mismo permiso de la burbuja. Sin él queda la notificación fija.
- **Comprobado en el Flip 4.**
  - Simulado con `adb shell cmd device_state state 0`, y luego cerrando el teléfono de verdad con la vigilancia
    activa: el orbe aparece en la pantalla exterior.
  - La vigilancia sigue: describió una foto con el teléfono cerrado.
