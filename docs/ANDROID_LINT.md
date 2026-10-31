# Android lint · triage (`lintDebug`)

Origen: informe de auditoría (Astra): `lintDebug` falla con 1 error y ~97 warnings.

## Comando

Desde `android/` (Git Bash):

```bash
export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
export JAVA_TOOL_OPTIONS="-Djdk.net.unixdomain.tmpdir=C:/aingel-java-socket-fallback-$RANDOM$RANDOM"
./gradlew.bat assembleDebug testDebugUnitTest lintDebug --console=plain
```

Informe: `android/app/build/reports/lint-results-debug.{txt,xml,html}`.

Sin `abortOnError false`, sin listas `disable`, sin baseline. Solo dos supresiones puntuales sobre falsos positivos verificados (ver abajo).

## Error original

| id | archivo:línea | causa | arreglo |
|---|---|---|---|
| `ContextCastToActivity` (androidx.activity.compose) | `app/src/main/java/ec/aingel/mobile/Foldables.kt:63` | `LocalContext.current as? Activity`: el `Context` de Compose no siempre es la `Activity` (puede ser un `ContextWrapper`), así que el cast puede dar `null` y la detección de pantalla externa (Flip) fallaría en silencio. | Se usa `LocalActivity.current` (activity-compose 1.10.1). |

## Resultado

| | antes | después |
|---|---|---|
| Errores | 1 | **0** |
| Warnings | 97 | **84** |
| `assembleDebug` | — | BUILD SUCCESSFUL |
| `testDebugUnitTest` | — | 64 tests, 0 fallos, 0 errores |

### Warnings por categoría

| Categoría | antes | después |
|---|---|---|
| Seguridad | 0 | 0 |
| Privacidad | 1 | 0 |
| Permisos Android | 0 | 0 |
| Cámara y micrófono | 0 | 0 |
| Servicios en segundo plano | 1 | 0 |
| Compatibilidad | 5 | 0 |
| Accesibilidad | 0 | 0 |
| Posibles errores en ejecución | 5 | 0 |
| Otros (cosmético / rendimiento / versiones) | 85 | 85 |

## Detalle de categorías relevantes

| Categoría | id | archivo:línea | estado |
|---|---|---|---|
| Privacidad | `DataExtractionRules` | `AndroidManifest.xml:16` | **fixed** — `android:fullBackupContent="false"` para API 26–30 (ya había `allowBackup="false"` y `dataExtractionRules` excluyendo todo en 31+). |
| Compatibilidad | `ContextCastToActivity` (error) | `Foldables.kt:63` | **fixed** — `LocalActivity.current`. |
| Compatibilidad | `ConfigurationScreenWidthHeight` ×2 | `Foldables.kt:66` | **fixed** — `LocalWindowInfo.current.containerSize` convertido a dp; `Configuration.screenWidthDp/HeightDp` cambia de semántica (insets) según targetSdk/versión. |
| Compatibilidad | `UnusedAttribute` ×2 (`showWhenLocked`, `turnScreenOn`) | `AndroidManifest.xml:23` | **fixed** — en API 26 `WatchCoverActivity` aplica `FLAG_SHOW_WHEN_LOCKED`/`FLAG_TURN_SCREEN_ON`; `tools:targetApi="27"` en la actividad documenta que los atributos son solo 27+. |
| Compatibilidad | `InlinedApi` | `VoiceInput.kt:23` | **fixed (falso positivo)** — `ERROR_SERVER_DISCONNECTED` es una constante `int` inlined; antes de API 31 el reconocedor nunca la emite y la comparación es `false`. `@SuppressLint("InlinedApi")` solo en `transientRecognizerError`, con comentario. Un guard `SDK_INT` rompería `HomeModesTest` (SDK_INT = 0 en JVM). |
| Errores en ejecución | `Recycle` ×2 | `SignVideo.kt:74` | **fixed (falso positivo)** — el `Surface` se guarda en el estado `surface` y se libera en `onSurfaceTextureDestroyed` y en `onDispose`; lint no sigue variables delegadas. `@SuppressLint("Recycle")` solo en `onSurfaceTextureAvailable`. |
| Errores en ejecución | `LocalContextResourcesRead` ×3 | `RedesignScreens.kt:212, 290, 291` | **fixed** — `LocalResources.current` (se recompone ante cambios de configuración). |
| Servicios en segundo plano | `InlinedApi` | `WatchService.kt:123` | **fixed** — el tipo de servicio en primer plano «cámara» se pide solo desde API 30 (`>= R`); antes, `startForeground` sin tipo. |

## Archivos protegidos: arreglos recomendados (no aplicados)

| archivo:línea | id | arreglo mínimo recomendado |
|---|---|---|
| `WatchService.kt:123` | `InlinedApi` (Servicios en segundo plano / cámara) | `FOREGROUND_SERVICE_TYPE_CAMERA` es API 30, pero el guard es `>= Q` (29). Cambiar a `if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) startForeground(NOTIFICATION, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA) else startForeground(NOTIFICATION, notification)` (o `ServiceCompat.startForeground(this, NOTIFICATION, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA)`). |
| `WatchService.kt:305, 327` | `ObsoleteSdkInt` (otros) | Quitar `Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&` y el `if/else` de `TYPE_APPLICATION_OVERLAY` (minSdk 26). |
| `WatchService.kt:86`, `ApiClient.kt:80, 93, 132, 155` | `UseKtx` (otros) | `prefs.edit { ... }` de `androidx.core.content`. Cosmético. |
| `values/strings_conversation.xml:50`, `values-en/strings_conversation.xml:49` | `PluralsCandidate` (otros) | Pasar a `<plurals>` y `pluralStringResource`. |
| `values/strings_conversation.xml:19–22, 45, 171, 173, 175` | `UnusedResources` (otros) | Borrar si el rediseño ya no los usa (`ui_conv_consent`, `ui_conv_what_sent*`, `ui_conv_need_consent`, `ui_vision_consent`, `ui_auth_*_d`) o volver a usarlos. |

## Warnings restantes (categoría «Otros»)

| id | n | ubicación | por qué queda |
|---|---|---|---|
| `GradleDependency` | 15 | `app/build.gradle.kts:24–34, 40–42, 44` | Versiones nuevas de AndroidX/Compose/CameraX. Fuera de alcance: no se actualizan dependencias aquí. |
| `NewerVersionAvailable` | 5 | `app/build.gradle.kts:35, 36, 38, 39, 43` | OkHttp 5, coroutines, org.json. Igual que arriba. |
| `UnusedResources` | 32 | `strings.xml:15, 19, 74, 109, 198, 199, 203, 205, 206, 211–221, 223`; `strings_network.xml:7, 19`; `drawable-nodpi/aingel_isotipo.png`; `strings_conversation.xml` (protegido, ver arriba) | Restos del flujo de configuración anterior. Limpieza aparte (también hay que borrar en `values-en`). |
| `UseKtx` | 15 | `AingelSigner.kt:234–236, 348`; `AudioRoute.kt:52, 53`; `CameraCapture.kt:30, 75`; `HomeScreen.kt:672`; `SoundSettings.kt:53`; `ApiClient.kt` y `WatchService.kt` (protegidos) | Estilo; equivalentes funcionales. |
| `PluralsCandidate` | 8 | `strings_redesign.xml:23, 66, 127` (+ `values-en` 22, 65, 126); `strings_conversation.xml` (protegido) | Gramática de i18n («1 rutinas»); requiere `<plurals>` y cambiar llamadas. |
| `Typos` | 3 | `strings_network.xml:5, 6`; `strings_redesign.xml:110` | Falso positivo: «momento» es español; lint asume inglés en `values/`. Se puede declarar `tools:locale="es"`. |
| `ObsoleteSdkInt` | 3 | `res/mipmap-anydpi-v26`; `WatchService.kt:305, 327` (protegido) | Limpieza: minSdk ya es 26. |
| `ModifierParameter` | 2 | `DesignSystem.kt:60, 137` | Convención de API Compose; cambiar el orden afecta a llamadas. |
| `ComposableNaming` | 1 | `SignTranslatorScreen.kt:77` | Convención de nombres. |
| `ViewConstructor` | 1 | `Hands3D.kt:345` | `Hands3DView` solo se crea desde código (`AingelHands3D.kt`), nunca desde XML ni el editor de layouts. |

## Archivos modificados

- `app/src/main/java/ec/aingel/mobile/Foldables.kt` — `LocalActivity` y `LocalWindowInfo.containerSize`.
- `app/src/main/java/ec/aingel/mobile/RedesignScreens.kt` — `LocalResources` en lugar de `LocalContext.current.resources`.
- `app/src/main/java/ec/aingel/mobile/VoiceInput.kt` — supresión puntual de `InlinedApi` (falso positivo).
- `app/src/main/java/ec/aingel/mobile/SignVideo.kt` — supresión puntual de `Recycle` (falso positivo).
- `app/src/main/java/ec/aingel/mobile/WatchCoverActivity.kt` — flags de ventana equivalentes en API 26.
- `app/src/main/AndroidManifest.xml` — `fullBackupContent="false"`, `tools:targetApi="27"` en `WatchCoverActivity`.

## Revalidación final (30-10-2026, después de las correcciones de privacidad)

`./gradlew.bat assembleDebug testDebugUnitTest lintDebug --console=plain`: `BUILD SUCCESSFUL`, 65 pruebas unitarias sin
fallos, lint con **0 errores y 84 advertencias**. Las 84 son de la categoría «otros»: 15 `GradleDependency` y 5
`NewerVersionAvailable` (no se actualizan dependencias en este PR), 31 `UnusedResources`, 15 `UseKtx`, 8
`PluralsCandidate`, 3 `ObsoleteSdkInt`, 3 `Typos` (falsos positivos en español), 2 `ModifierParameter`, 1
`ComposableNaming` y 1 `ViewConstructor`. Ninguna afecta a seguridad, privacidad, permisos, cámara o micrófono,
servicios en segundo plano, compatibilidad, accesibilidad ni errores de ejecución. Se borró el texto sin uso
`synthetic_confirm` (la declaración del cliente ya no existe).
