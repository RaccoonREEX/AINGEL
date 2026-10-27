# Android local — 27 de octubre de 2026

Existe un APK debug compilado en `android/app/build/outputs/apk/debug/app-debug.apk`. Es una aplicación nativa Kotlin/Compose, no una web embebida. Instalado y arrancado en Samsung SM-F721B con Android 16 mediante USB. Una prueba instrumentada en ese teléfono verificó el cliente nativo, la sesión cifrada y los contratos de cuidado, memoria y MFA contra el backend local. También pasó el recorrido de pantallas de registro/perfil/preferencias/rostros/seguridad/logout y una prueba de las ocho orientaciones EXIF con imágenes sintéticas. No certifica todavía cámara, voz ni precisión facial.

## Compilar

Requiere JDK 17+ (se usa el JBR de Android Studio si está instalado), Android SDK con plataforma 36 y acceso a Google Maven/Maven Central. El wrapper fija Gradle 8.14.3 y su SHA-256 oficial.

```powershell
.\Build-Android.ps1
```

Ejecuta `assembleDebug testDebugUnitTest lintDebug`. El lanzador genera `local.properties` ignorado por Git y aplica solo al proceso de compilación una solución para el fallo de sockets Unix de Java en este Windows. No cambia configuración global. No hay firma de distribución ni publicación en Play Store.

## Instalar cuando esté listo el teléfono

El teléfono ya fue conectado y autorizado. Para repetir con un único dispositivo autorizado:

```powershell
.\Start-Aingel.ps1
.\Build-Android.ps1 -Install
```

El segundo comando valida, configura `adb reverse tcp:8010 tcp:8010`, instala y abre AINGEL. La dirección predeterminada es `http://127.0.0.1:8010/`. El teléfono necesita mantener USB y la redirección; no se abre el servidor a la red local. La variante debug permite HTTP solo para loopback/localhost y `10.0.2.2`. Fuera de debug se exige HTTPS. No hay backend público disponible todavía.

## Flujos implementados y comprobaciones pendientes

| Área | Implementado en código | Prueba pendiente en dispositivo |
|---|---|---|
| Cuenta | Registro/logout en UI y cliente nativo, sesión CSRF, desafío TOTP/recuperación verificados en el Samsung | Reinicio, expiración, cambio de cuenta y escaneo Authenticator |
| Seguridad | Cookies AES-GCM con Android Keystore, backups deshabilitados, capturas bloqueadas, clave Meta solo en servidor | Reiniciar dispositivo, invalidación de clave y recent apps |
| Cuidado | Selección de perfiles, cuidadores, rutinas, ajustes de comunicación y botón de apoyo local; recorrido con datos sintéticos aprobado | Dos cuentas y cambios sincronizados con Care web |
| Memoria | Observación humana actual confirmada, consulta exacta, lectura y eliminación | No evidencia, permiso denegado y fechas |
| Conocimiento | Búsqueda educativa MedlinePlus con fuente y fecha en Preguntar | Actualización del índice y evaluación de comprensión con usuarios |
| Rostros | Activación por principal, registro propio de 1–3 fotos por familiar, revocación, consulta local, posible coincidencia y TTS | Fotos consentidas, desconocidos, luz, ángulos, gafas, parentescos y falsos positivos |
| Cámara | CameraX con captura JPEG en memoria y selección de archivo; permisos solicitados por acción | Permiso denegado, cámara delantera/trasera, rotación y distintas marcas |
| Ver | Imagen sintética incluida, Spark/SAM por backend y lectura del resultado | Petición real desde APK, orientación y visualización |
| Oír | AudioRecord PCM24kHz, relay autenticado, parciales acumulativos, finalización y cierre al salir/background | Micrófono, ritmo, permisos, latencia, interrupción/red y audio sintético |
| Comunicar | Frases AAC y TTS del sistema | Voces instaladas, idioma, volumen y audibilidad |
| Accesibilidad | Recursos español/inglés, controles de 52dp, escala del sistema, texto grande, contraste | TalkBack, orden de foco, tamaño máximo y pantallas pequeñas |

Las trece pruebas JVM cubren restricción HTTPS/loopback, rechazo de URLs con credenciales, reemplazo de parciales, final sin texto, protección del texto final y límite de historial. Las cinco pruebas instrumentadas aprobadas son `DeviceBackendTest`, `NativeScreenTest`, `PhotoOrientationTest`, `SignClipTest` y `CompanionContractTest`. La prueba `NativeScreenTest` verifica además el saludo configurable, presentación uno por uno, botón de apoyo, preferencia LSEC, control de consentimiento sintético para Spark, consulta de MedlinePlus y que la alergia sintética guardada reaparece al abrir de nuevo Preferencias. La prueba `PhotoOrientationTest` verifica dimensiones y píxel de referencia en las ocho orientaciones EXIF, antes de retirar metadatos.

La prueba instrumentada `DeviceBackendTest` ejecutó registro, creación de perfil/rutina, confirmación, búsqueda sin evidencia y con memoria, recuperación de cookies desde Android Keystore, activación TOTP, desafío de acceso, rechazo de contraseña sola, recuperación de un solo uso, rechazo de reutilización y desactivación con contraseña+recuperación. Usa una cuenta sintética y preferencias separadas de las de la app normal. Los 89 tests backend cubren permisos/aislamiento, círculo, memoria, MFA y lógica de plantillas; los tests de rostros usan vectores sintéticos y no miden precisión real.

Rutinas móviles: creación diaria, eliminación y confirmación manual; edición de días específicos y detalles completos se realiza en Care web. No hay notificaciones/alarmas de fondo. Configuración de permisos individuales y cancelación de invitaciones pendientes también están completas en Care web. Los fallos de red o validación se muestran con un mensaje general, pendiente mejorar su detalle y reintentos.

No subir fotos/voces personales a Spark/SAM/Voice mientras siga pendiente la revisión de condiciones de créditos Meta. El reconocimiento de familiares se procesa en el backend local, con fotos transitorias y plantillas cifradas. No tiene liveness ni sirve como autenticación. No hay resultados de precisión facial publicados.

Para repetir las pruebas del teléfono, después de `adb reverse` y con la app en la pantalla de inicio de sesión:

```powershell
.\Build-Android.ps1 -DeviceTests
```

El lanzador aplica el JDK/opción local de sockets y la redirección USB automáticamente. `NativeScreenTest` requiere sesión cerrada y no expulsa a una cuenta existente. Los informes completos del teléfono contienen identificadores/logs y se conservan solo en carpetas ignoradas; no publicarlos.

La reproducción de clips reales de señas aún no se ha probado: el catálogo está vacío. El test de transporte usa datos sintéticos y no demuestra que exista una traducción. La prueba de contrato de conversación usa un servidor simulado; se verificó una llamada real sintética a Spark por separado.
