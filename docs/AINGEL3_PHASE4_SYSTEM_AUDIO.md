# AINGEL 3.0 · Fase 4: subtítulos del audio del equipo (31-10-2026)

Rama `feat/aingel3-system-audio`, apilada sobre `feat/aingel3-documents` (PR #8). No está fusionada ni desplegada.
No cambia el backend: usa los subtítulos en vivo que ya existían (`/ws/captions/`, Meta Voice Transcribe).

## Qué se construyó (AINGEL Desktop)

- **`LoopbackCapture`:** WASAPI *loopback* del dispositivo de salida predeterminado, con las interfaces COM
  declaradas a mano y sin NuGet.
  - Captura solo lo que suena por los altavoces, nunca el micrófono.
  - Entrega fragmentos de 200 ms, el máximo que acepta el servidor.
  - Cuando no suena nada, rellena con silencio al ritmo real, para que el servicio pueda cerrar la frase. Nunca va
    más rápido que el tiempo real, que es el límite del servidor.
- **`PcmConverter`:** convierte el formato de mezcla de Windows a 24 kHz, mono y 16 bits, con interpolación que
  continúa entre fragmentos.
  - Formatos de entrada: float de 32 bits y PCM de 16, 24 y 32 bits.
  - El audio de 16 bits pasa sin cambios.
- **`CaptionsClient`:** el WebSocket del servidor.
  - Usa la cookie de sesión y el `Origin` del propio servidor.
  - El mensaje de inicio lleva el perfil y, solo si se elige, la declaración de prueba privada. Nunca dice
    «synthetic» ni «fixture».
  - El servidor mantiene sus comprobaciones: permisos de micrófono y voz, revisados cada 5 s, y límite de ritmo.
- **`CaptionAssembler`:** convierte los eventos en frases.
  - En vivo, Meta envía parciales acumulados y termina el turno con `speechComplete` y con un evento final **sin
    texto**. Por eso la frase final es el último parcial cuando el final viene vacío, y se emite una sola vez.
  - El hablante solo se nombra si Meta lo informa.
- **Ventana «Subtítulos del audio del equipo»** (Ctrl+Alt+C o su botón):
  - **Indicadores:** punto rojo y título «● Subtitulando» mientras captura.
  - **Confirmación en cada inicio:** el audio va a Meta y, si se oyen otras personas, deben saberlo y aceptarlo.
  - **Pantalla:** la frase actual en letra grande, y la transcripción con hora en un cuadro de solo lectura que se
    recorre con las flechas.
  - **Opciones:** tamaño de letra y anuncio de cada frase al lector de pantalla (activado por defecto si hay uno).
  - **Prueba privada:** solo con audio propio, con su propia confirmación.
  - **No guarda la transcripción:** «Borrar» la quita de la pantalla.
  - **Renovación:** la sesión se renueva sola a los 9,5 minutos, antes del límite de 10 minutos del servidor.

## Pruebas ejecutadas en este Windows

- **Compilación:** sin errores ni avisos.
- **`AingelDesktop.Tests`:** 82 comprobaciones, todas correctas. Las de audio:
  - un tono de 440 Hz en 48 kHz estéreo float, en fragmentos desiguales, da 24 000 muestras con amplitud y tono
    conservados (440 ciclos);
  - 16 bits a 24 kHz pasa sin cambios;
  - 8 bits se rechaza;
  - el formato extensible float se lee bien;
  - el mensaje de inicio no lleva la declaración salvo que se elija, y solo en el perfil propio;
  - las URL `wss`/`ws`;
  - los eventos se leen bien;
  - el ensamblador: el final vacío usa el último parcial, se emite una vez, el texto final prevalece y no hay
    hablante si no se informa;
  - **una captura *loopback* real de 1,25 s:** formato leído y 6 fragmentos de 9600 bytes, al ritmo real.
- **Prueba G (reunión) en vivo con Meta, con voz sintética:**
  - **Audio:** una reunión ficticia, con guion escrito aquí, leída por la voz de Windows «Microsoft Helena»
    (español): 13,9 s. Nadie real habla.
  - **Ruta:** se envió en tiempo real por el WebSocket del servidor local, en modo Meta, con la prueba privada de un
    perfil local de prueba.
  - **Resultado:** la transcripción final fue exacta: «Buenos días a todos. Empezamos la reunión del lunes. Primero
    revisamos el presupuesto del proyecto. Después Carla enviará el informe. La próxima reunión será el jueves a las
    tres de la tarde.»
  - **Error encontrado:** la primera ejecución no mostró ninguna frase, porque el final llega sin texto. Se corrigió
    con `CaptionAssembler`.
- **La ventana, revisada con UI Automation** y sin pulsar «Empezar», así que no se capturó audio real del equipo:
  - todos los controles tienen nombre;
  - el estado inicial dice «No se captura ningún audio».

## Privacidad (sin cambios en el servidor)

- **Interruptor:** el audio solo se captura mientras la persona tiene los subtítulos en marcha, con indicadores
  visibles. Al detener o cerrar la ventana se libera el dispositivo.
- **Voces de otras personas:** una reunión real contiene voces de terceros. En el servidor de pruebas privadas actual
  (`PRIVATE_OWN_MEDIA_TEST=1`), la declaración es solo para audio propio. Por eso, subtitular reuniones con otras
  personas **no** está cubierto hasta que se usen los permisos normales (`AINGEL_REAL_DATA` con permisos de micrófono
  y voz), y aun así esas personas deben saberlo. Es decisión tuya y de Astra activarlo; aquí no se cambió nada.

## Límites

- **Hablantes:** Meta no envió etiquetas de hablante en la prueba (una sola voz). No se verificó la separación de
  varias voces. La aplicación solo las muestra si llegan.
- **Turnos:** la voz sintética no hizo pausas y toda la reunión fue un único turno. Con habla real, las pausas cierran
  las frases antes.
- **Dispositivo de salida:** si cambia durante la captura (por ejemplo, al conectar unos auriculares), hay que detener
  y volver a empezar.
- **Renovación:** puede perder alrededor de un segundo de audio entre una sesión y la siguiente.
- **Contenido protegido:** el audio protegido (algunas apps con DRM) puede llegar en silencio, y AINGEL no lo evita.
- **NVDA:** no se probó, porque no está instalado aquí.

## Despliegue y reversión

- **Despliegue:** solo es la aplicación de escritorio y no hay cambios en el servidor. Debe permitir el origen
  `https://aingel.mapatechstudio.com` en `AINGEL_WEBSOCKET_ORIGINS`, igual que la web.
- **Reversión:** revertir el commit.
