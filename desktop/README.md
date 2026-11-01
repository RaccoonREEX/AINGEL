# AINGEL Desktop para Windows (experimental)

Una ventana pequeña de AINGEL, siempre visible si quieres, que describe lo que hay en tu pantalla con la visión
profunda del servidor (`/api/v1/vision/`, fuente `screen`). Usa la misma cuenta y los mismos permisos que la web y el
móvil.

## Atajos

| Atajo | Acción |
|---|---|
| Ctrl+Alt+D | Describir la ventana activa |
| Ctrl+Alt+P | Describir la pantalla completa (el monitor de la ventana activa) |
| Ctrl+Alt+Q | Capturar la ventana activa y escribir una pregunta sobre ella. Intro envía y Escape descarta. |
| Ctrl+Alt+M | Explorar a fondo la última imagen (seguimiento, 3 pasos) |
| Ctrl+Alt+F | Leer el elemento con el foco del teclado. Es local, no envía nada y nunca lee contraseñas. |
| Ctrl+Alt+O | Abrir un documento PDF o una foto de página (fase 3) |
| Ctrl+Alt+C | Subtítulos del audio del equipo: reuniones, vídeos (fase 4) |
| Ctrl+Alt+S | Detener la voz |
| Ctrl+Alt+A | Mostrar u ocultar AINGEL |

Si otro programa ya usa un atajo, AINGEL lo indica y el botón sigue funcionando. No se usan Ctrl+Alt+N (que inicia
NVDA) ni Ctrl+Alt con las flechas (navegación de tablas de NVDA).

## Privacidad

- **Capturas:** AINGEL captura solo cuando lo pides con un atajo o un botón, nunca en segundo plano, y lo dice
  («Capturando: …»). Su propia ventana queda fuera de las capturas (`SetWindowDisplayAffinity`).
- **Contenido protegido:** el vídeo con DRM o las ventanas excluidas de captura salen en negro. AINGEL no lo evita.
- **Envío:**
  - La imagen se envía al servidor de AINGEL y de ahí a Meta. Para las preguntas de seguimiento, el servidor la
    guarda cifrada hasta 15 minutos.
  - Al pedir otra imagen, o al cerrar sesión o la ventana, AINGEL la borra en ese momento.
- **Permisos:**
  - El servidor exige en cada captura los permisos de imágenes de la persona: «Usar la cámara» y «Enviar fotos a
    Meta», en Personalizar.
  - En el servidor de pruebas privadas, exige además la casilla «Prueba privada de mi propia pantalla», que solo
    está disponible en el perfil propio y pide confirmación.
- **Prueba sintética:** la casilla «Modo de prueba sintética» no captura nada. El servidor describe una pantalla de
  Windows ficticia que él mismo dibuja.
- **Sesión:** se guarda cifrada con DPAPI para tu usuario de Windows en `%LOCALAPPDATA%\AINGEL\Desktop`. «Cerrar
  sesión» la borra.

## Subtítulos del audio del equipo

- **Qué se captura:** WASAPI *loopback* del dispositivo de salida predeterminado, es decir, lo que suena por los
  altavoces, nunca el micrófono.
- **Envío:** el audio se convierte a 24 kHz mono y se envía al servidor de AINGEL, y de ahí a Meta Voice Transcribe.
  Se transcribe solo mientras la ventana de subtítulos está en marcha, con un punto rojo y el título
  «● Subtitulando».
- **Confirmación:** cada inicio pide confirmar. Si se oyen otras personas, deben saber y aceptar que sus voces se
  transcriben con IA.
- **Permisos:** el servidor exige «Usar el micrófono» y «Enviar voz a Meta», o la prueba privada con audio propio.
  Los vuelve a comprobar cada 5 segundos.
- **Transcripción:**
  - Solo se muestra; AINGEL no la guarda.
  - Se ve en letra grande y ajustable, y cada frase puede anunciarse al lector de pantalla.
  - Quien habla solo se nombra si el servicio lo informa: AINGEL no lo adivina.
- **Sesiones:** se renuevan solas antes del límite de 10 minutos del servidor.

## Accesibilidad

- **Etiquetas:** todos los controles tienen nombre para UI Automation, la interfaz que leen NVDA, JAWS y Narrador.
- **Avisos:**
  - El estado se anuncia como región en vivo.
  - Con un lector de pantalla activo, AINGEL no usa su propia voz, para que no se superpongan, y la respuesta se
    anuncia al lector. Se puede activar «Voz de AINGEL» si se prefiere.
- **Respuesta:** queda en un cuadro de solo lectura que se recorre con las flechas.
- **Teclado:** el foco es visible con un anillo ámbar de 3 px, y todo se usa con teclado.
- **Movimiento:** el orbe deja de animarse si Windows tiene desactivadas las animaciones.

## Compilar

Hace falta el SDK de .NET 8 o posterior. No se descarga ningún paquete NuGet.

```powershell
.\desktop\Build-Desktop.ps1
```

Compila, ejecuta las comprobaciones (`AingelDesktop.Tests`) y publica en `desktop\dist`. Para ejecutarlo hace falta
el **.NET 8 Desktop Runtime** de Microsoft.

**Instalador:** `.\desktop\Build-Installer.ps1` crea `desktop\dist-installer\AINGEL-Desktop-Setup-<versión>.exe` y
`manifest.json`. Es por usuario, sin administrador, y verifica su SHA-256. Los detalles y el proceso de publicación
están en `docs/AINGEL3_PHASE6_INSTALLER.md`.

Para probar contra un servidor local en modo de prueba, se ejecutan las comprobaciones de API así:

```powershell
$env:AINGEL_TEST_BACKEND = "http://127.0.0.1:8010/"
$env:AINGEL_TEST_USER = "<usuario de prueba local>"
$env:AINGEL_TEST_PASSWORD = "<su contraseña>"
dotnet desktop\AingelDesktop.Tests\bin\Release\net8.0-windows\AingelDesktop.Tests.dll
```
