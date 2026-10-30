# AINGEL · versión local para pruebas

**Adaptive Intelligence for Navigation, Guidance & Everyday Living**

AINGEL adapta la información a cómo cada persona puede ver, escuchar, comunicar y recordar. Estado actual: aplicación web y backend local funcionales, más APK Android debug compilado. Instalado en un Samsung con Android 16, con prueba instrumentada de sesión/cuidado/memoria/MFA aprobada; el despliegue público sigue pendiente.

## Abrir y probar

La aplicación local está en **http://127.0.0.1:5173/**. Para volver a arrancarla en Windows:

```powershell
.\Start-Aingel.ps1
```

El lanzador conserva la base de datos, aplica migraciones, crea cuentas sintéticas solo la primera vez y limpia registros vencidos. Busca el archivo de clave Meta ya autorizado en el Escritorio; también acepta `-ModelKeyFile '<ruta local>'`. Sin clave, visión usa un modo de prueba explícito y los subtítulos no simulan inferencia.

Las cuentas sintéticas y sus contraseñas están **solo** en `.local/demo-accounts.json`, ignorado por Git. `aingel.demo` es el usuario principal, `familia.demo` tiene permiso para configurar pero no para ver recuerdos y `externo.demo` no tiene acceso. También puedes crear cuentas desde la interfaz. No uses datos reales todavía en pruebas que envíen contenido a Meta.

[Guía de pruebas paso a paso](docs/TESTING_GUIDE.md) · [Estado y límites](docs/KNOWN_LIMITATIONS.md).

[Rediseño de interfaz y Thinking Orbs](docs/UI_REDESIGN.md). · [Conversación, visión y lengua de señas](docs/CONVERSATION_VISION_SIGNS.md) · [Inventario de licencias](docs/THIRD_PARTY_INVENTORY.md).

## Funciones disponibles

- Registro, inicio/cierre de sesión, CSRF y verificación TOTP compatible con Google Authenticator. QR local, secreto cifrado, recuperación de un solo uso, rechazo de códigos reutilizados y límite de intentos. Cada cuenta activa su propio 2FA desde Seguridad.
- Un perfil principal por cuenta y acceso delegado a otros perfiles. Círculo de **1 a 4 cuidadores aceptados**. Cero miembros es borrador; nunca se impide revocar al último cuidador. Las invitaciones privadas vencen a los 7 días y reservan plaza.
- Permisos independientes de configuración y lectura de recuerdos. Invitación/gestión de miembros solo por el principal; el familiar puede salir por sí mismo.
- Preferencias de accesibilidad y comunicación por perfil: nombre y trato, saludo, ritmo de voz y presentación de una actividad a la vez. El botón de apoyo responde con una frase local según la preferencia. La familia también configura zona horaria, necesidades, alergias y contacto de referencia.
- Rutinas de sueño, despertar, medicinas, baño, comidas, agua, citas y otras actividades, con días/horarios e instrucciones humanas. Confirmaciones manuales con autor; los avisos requieren tener abierta la pantalla Hoy.
- Búsqueda educativa local en 2.028 resúmenes de salud de MedlinePlus con fuente y fecha. Se puede seleccionar una fuente para una pregunta sintética a Spark; es una respuesta aislada, experimental y no modifica el plan de cuidados.
- Mensajes con autor, fecha e idioma original; consultas locales de rutinas/mensajes y búsqueda exacta del último recuerdo de un objeto. Sin evidencia, no se inventa una ubicación.
- Recuerdos confirmados por el principal, fotos privadas opcionales, eliminación y retención de 7 días. El cuidador con permiso de lectura no puede crear memorias por la persona.
- Visión y conversación sintética con `muse-spark-1.3`, búsqueda de objetos con `sam-3.1`, recuadros y máscaras decodificadas mediante el parser oficial, lectura opcional del resultado con la voz del navegador.
- Subtítulos en vivo con `muse-voice-transcribe-1.0`, AudioWorklet PCM24kHz y relay WebSocket autenticado. Sin grabación; una sesión por cuenta, máximo 10 minutos.
- Reconocimiento **experimental y local** de familiares con YuNet/SFace. Desactivado por defecto; requiere autorización del principal y registro de 1–3 fotos propias distintas por el familiar adulto, con filtros de nitidez y consistencia. Plantillas cifradas por 30 días, revocables. No se conservan las fotos ni se envían a Meta. Resultados posibles, sin garantía de identidad ni liveness.
- Inicio móvil 5a: menú superior derecho según el perfil (sordera: escuchar, ver y escribir y traducir; ceguera: ver y describir, vigilancia continua en segundo plano) y Ajustes de sonido y voz 5b (salida de audio, micrófono, control por voz). La conversación es continua, puede buscar en la web y AINGEL usa las funciones de la app cuando se le piden por voz (mirar, buscar un objeto, vigilar, traducir a señas). Ver [docs/HOME_AND_SETTINGS.md](docs/HOME_AND_SETTINGS.md).
- Plegables: en pantallas exteriores solo el orbe de AINGEL sobre negro (tocar para hablar); en el Fold, pantallas dobles o en horizontal, dos paneles (AINGEL y manos | opciones). Icono adaptativo nuevo de la APK. Auditoría de conexiones web–Android–servidor del 29-10-2026 en el mismo documento.
- Traductor de señas: AINGEL signa con manos articuladas en 3D (three.js, con respaldo 2D) (alfabeto, números y 43 palabras y acciones de diseño AINGEL, pendientes de validar en LSEC); botón «Traducir» con cuatro modos (voz/texto a señas, señas a voz/texto con tablero de pictogramas). Sin reconocimiento automático ni gramática completa de LSEC.
- Interfaz centralizada en español/inglés, texto grande, contraste y diseño adaptable. No implica soporte completo de los 19 idiomas previstos ni certificación de accesibilidad.

## Verificación realizada

89 pruebas backend y trece pruebas JVM Android pasan, compilación TypeScript/Vite y comprobación de dependencias correctas. En Edge: login, cambio de idioma, configuración por familiar, bloqueo de recuerdos, guardado y consulta sin evidencia, descripción real de una imagen sintética. En un marco real de 390 px, el documento móvil no presenta desbordamiento horizontal. TalkBack y lectores de pantalla no se han auditado todavía.

Llamadas reales, todas con material sintético: Spark (2.344 s observados), SAM con máscara y caja (2.281 s), Voice por el relay local (4.455 s de audio, 8 parciales y frase final correcta). No son benchmarks de precisión. Los informes están en `docs/*SMOKE_RESULT.json`, `META_SPARK_RECHECK.json` y `META_SAM_RECHECK.json`.

## Instalación desde cero

Python 3.12 y Node compatible con Vite (20.19+ o 22.12+):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
Set-Location web
npm ci
npm run build
Set-Location ..
.\Start-Aingel.ps1
```

El reconocimiento facial requiere instalar los pesos oficiales localmente. La búsqueda educativa requiere preparar el índice local:

```powershell
.\.venv\Scripts\python.exe backend\scripts\setup_face_models.py
.\.venv\Scripts\python.exe backend\scripts\import_medlineplus.py
```

Modelos, claves, contraseñas de prueba, base local y medios están excluidos de Git. El lanzador solo escucha en loopback. `Stop-Aingel.ps1` detiene únicamente los procesos que haya iniciado y registrado el lanzador; servidores iniciados en una terminal se detienen desde esa terminal.

## Variables y secretos

`.env.example` documenta variables, pero no hay carga automática de `.env`. `MODEL_API_KEY` solo existe en el proceso servidor. `AINGEL_AI_MODE=mock|meta`; `AINGEL_SYNTHETIC_TESTS_ONLY=1` limita los envíos de prueba por aserción del usuario, sin detector automático de contenido sensible. El aviso de uso de contenido con créditos gratuitos sigue pendiente para datos reales.

`DJANGO_SECRET_KEY` debe ser estable. El lanzador la conserva en `.local/server-secret.txt`; la clave Fernet de TOTP/plantillas está en `.local/encryption.key`. Conserva ambas de forma privada con los respaldos. Fuera del modo local, configura `AINGEL_ENCRYPTION_KEY` mediante gestión de secretos. No publiques esta configuración como un despliegue seguro.

## Datos y documentación

Se preparó un subconjunto local de 30 anotaciones de validación VizWiz (CC BY 4.0), con manifiesto y herramienta de evaluación de respuesta/no respuesta. No se descargaron fotos del corpus ni se entrenó un modelo. LSEC y los corpus clínicos/restringidos siguen fuera de uso. Los pesos faciales no son un dataset de familiares.

[Conocimiento y lengua de señas](docs/KNOWLEDGE_AND_SIGNS.md) · [Arquitectura](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Privacidad](docs/PRIVACY.md) · [2FA y rostros](docs/SECURITY_AND_FAMILY.md) · [Datasets](docs/DATASET_RESEARCH.md) · [Accesibilidad](docs/ACCESSIBILITY.md) · [Idiomas](docs/LOCALIZATION.md) · [Reglas](docs/HACKATHON_RULES.md) · [Despliegue](docs/DEPLOYMENT.md) · [Halo futuro](docs/HALO_VISION.md).

Existe un APK debug nativo con cámara, audio, sesión, MFA, círculo y reconocimiento familiar conectados al backend. [Instalación y pruebas Android](docs/ANDROID_TESTING.md). Instalado y arrancado en Samsung SM-F721B/Android 16; falta validar cámara, micrófono y precisión con familiares. No hay dominio público, notificaciones en segundo plano, traducción a lengua de señas ni validación de precisión facial con familiares reales. Halo es un concepto futuro. La selección de licencia del proyecto y revisión completa de avisos de terceros quedan pendientes antes de publicar.
