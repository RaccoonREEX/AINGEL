# Rediseño de AINGEL (UI v1.1.1)

La web implementa el paquete de diseño **AINGEL_UI_v1.1.1** (maqueta `AINGEL_Rediseno_v1.1.1.html`, `tokens.json`, `ESPECIFICACION_UI_UX.txt`, `ONBOARDING_Y_PRESETS.txt`, `IMPLEMENTACION_ORB.txt`). Las pantallas usan el backend real; la maqueta no es fuente de datos.

## Pantallas web

| Maqueta | Implementación |
| --- | --- |
| 2a Iniciar sesión · 2b Crear cuenta | `web/src/screens/Auth.tsx` (en móvil: 1e Acceso, 2d, 2e) |
| 2c Configurar AINGEL en 4 pasos | `web/src/screens/Onboarding.tsx` (en móvil: 2f, 2g, 2h) |
| 1b Inicio · 1c Conversación | `web/src/screens/Home.tsx` (en móvil: 1f, 1g, 1h) |
| 1d Hoy | `web/src/screens/Routines.tsx` (en móvil: 1i) |
| 1j Más | `MorePage` en `web/src/App.tsx` |

Navegación: barra lateral de 240 px en escritorio; en móvil (≤ 760 px) barra inferior AINGEL · Hoy · Recordar · Círculo · Más. Ver, Escuchar y Recordar se ocultan según las preferencias del perfil, como antes.

**Configuración inicial.** Condiciones con nivel y comunicación generan la configuración predefinida. Se guardan en el servidor: `visual_assistance`, `hearing_assistance`, `memory_assistance`, `large_text`, `high_contrast`, `voice_output`, `reduced_motion`, `simple_instructions`, y en comunicación `preferred_name`, `addressing`, `pace`, `interaction`, `sentence_length`, `sign_language`. Las claves sin soporte en el servidor (`voice_first`, `text_first`, `haptic_alerts`, `no_reading`, `routine_preview`, `simplified_home`, `can_configure`) se muestran como «próximamente» y quedan anotadas en las notas de apoyo del perfil.

**Asistente por voz.** El botón de micrófono abre el micrófono solo tras pulsarlo. El texto se obtiene con el reconocimiento de voz del navegador cuando existe; si no está disponible o falla, se ofrece escribir. Las respuestas son locales y con procedencia: rutinas de hoy, últimos mensajes del círculo y última observación guardada de un objeto. Sin datos, AINGEL lo dice; no inventa. Una petición no reconocida pasa al estado «confundido».

## AingelOrb y audio

`web/src/components/aingel/`:

- `orb-core.ts`: renderer en canvas portado de `aingel-orb.js` del paquete v1.1.1 (misma distribución de puntos Fibonacci, banda dorada, cara, ojos con parpadeo, órbitas, parámetros por estado, activación y deformación por audio).
- `AingelOrb.tsx`: componente React. Props `state`, `audioLevel` (número o lector por fotograma), `configured`, `size`, `face`, `eyes`, `arcs`, `tone`, `reducedMotion`. No abre el micrófono.
- `useAudioLevel.ts`: RMS en dominio temporal, `fftSize` 1024, suavizado 0.65, puerta 0.02, curva 0.65, ataque 0.35, liberación 0.10.
- `useMicrophoneLevel.ts`: micrófono con cancelación de eco; detiene las pistas al terminar.
- `useOutputAudioLevel.ts`: nivel de un `<audio>` (para un proveedor de voz futuro) y, para la síntesis de voz del navegador, que no expone muestras, un nivel guiado por los límites de palabra reales de la locución.

Fuente del nivel: escuchando → micrófono; respondiendo → salida de AINGEL; resto → 0. Nunca se usa el micrófono mientras AINGEL habla. Sin fuente, el orb queda en reposo (no hay voz simulada).

El orb sigue el diseño aprobado y no incluye código del paquete `@yogesharc/thinking-orbs` (retirado de `web/package.json` y de los recursos Android). Avisos: `THIRD_PARTY_NOTICES.md` en la raíz.

## Android

Pantallas 1e (Acceso), 2d, 2e, 2f-2h (configuración y activación), 1f-1h (inicio, escuchando, respuesta), 1i (Hoy) y 1j (Más) en `RedesignScreens.kt`, con los tokens y la tipografía Montserrat de `DesignSystem.kt`. El resto de pantallas conserva sus controles bajo la nueva cabecera y la barra inferior.

- `AingelOrb.kt`: el mismo renderer que la web, en Compose Canvas.
- `VoiceInput.kt`: reconocimiento de voz del sistema (`SpeechRecognizer`); su `onRmsChanged` da el nivel real del micrófono para el orb, sin abrir el micrófono dos veces. Sin reconocedor, un medidor `AudioRecord` mueve el orb y se ofrece escribir.
- Voz de AINGEL: `TextToSpeech` con `onRangeStart` (palabra a palabra) como nivel de salida.
- `SetupPresets.kt` y `Today.kt`: reglas de configuración predefinida, resumen de Hoy e intenciones, con pruebas unitarias.
- El permiso de micrófono se pide al tocar el botón. Las capturas de pantalla siguen bloqueadas (`FLAG_SECURE`); solo una compilación debug abierta con `--ez aingel_qa_screenshots true` las permite para revisión de diseño.

Probado en Samsung Galaxy Z Flip 4 (SM-F721B, Android 16, tamaño de fuente del sistema 1,15).

## Pendiente

- Revisión con lectores de pantalla y TalkBack.
- Probar el reconocimiento de voz real en el teléfono (requiere conceder el permiso de micrófono).
- El reconocimiento de voz del navegador puede procesar el audio en servicios del fabricante del navegador; revisar antes de usar con datos reales.
