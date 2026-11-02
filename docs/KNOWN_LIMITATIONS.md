# Límites actuales (2-11-2026, rama `release/hackathon-submission-2026`)

Sustituye la versión del 27-10-2026, que describía una versión local anterior a AINGEL 3.0.

## Evidencia y validación

- **Sin estudio con usuarios:** AINGEL no se ha validado en un estudio con personas con discapacidad. La
  accesibilidad sigue pautas (contraste, texto grande, lectores de pantalla, teclado) y pruebas del proyecto. Ni
  NVDA ni TalkBack tienen todavía un recorrido completo documentado.
- **Pruebas automáticas con Meta:** interceptan el cliente HTTP. Demuestran lo que AINGEL envía, los permisos y las
  cuotas, **no** la precisión de las respuestas de Meta. Las llamadas reales a Meta se hicieron con material
  sintético y cuentas ficticias (`docs/VALIDACION_ASTRA_PR12_2026-11-01.md`). La visión profunda completa contra
  Meta real quedó pendiente en staging.
- **Descripción de personas:** se basa en una sola foto o fotograma. La expresión se describe como apariencia y
  nunca prueba lo que alguien siente. No hay una evaluación de su precisión.
- **Tipo de imagen:** Meta decide si recibió una fotografía, un dibujo, una ilustración o una foto de una hoja con un
  dibujo, siguiendo las instrucciones de AINGEL. No se ha medido con qué precisión lo distingue; las pruebas solo
  verifican las instrucciones (`docs/VISION_CONTENT_TYPE.md`).

## Funciones experimentales o desactivadas

- **Reconocimiento facial de familiares:** desactivado (`AINGEL_FACE_RECOGNITION_ENABLED=0`). No forma parte del
  producto ni de la demo.
- **Vigilancia continua por vídeo:** experimental y desactivada para datos reales en producción
  (`AINGEL_VIDEO_REAL=0`).
- **Señas:**
  - el avatar muestra 81 diseños propios (alfabeto, números y 43 palabras), **ninguno validado todavía** por
    personas señantes en el registro de señas;
  - no es una traducción de la LSEC; el reconocimiento de señas por cámara es experimental.
- **Idiomas:** la interfaz está en español e inglés. Otros idiomas no están implementados.

## Plataformas

- **Android:**
  - la APK candidata pasó en un Samsung SM-F721B el registro, el perfil, la sesión y el MFA contra un backend de
    prueba;
  - faltan en dispositivo la cámara con Meta real, la visión profunda y TalkBack.
- **Desktop:**
  - las comprobaciones locales cubren campos, consentimientos y la exclusión de las ventanas de AINGEL de las
    capturas;
  - la prueba integral contra staging (captura, descripción, PDF y subtítulos) sigue pendiente;
  - requiere el runtime de escritorio de .NET 8.
- **Web:** usa Montserrat desde Google Fonts, lo que revela la dirección IP del navegador a Google. Se puede
  alojar la fuente si se quiere evitarlo.

## Datos, costes y cumplimiento

- **Topes de gasto:** son una estimación de AINGEL, no la factura de Meta. Una petición que falla antes de que Meta
  responda no se cuenta.
- **Territorios restringidos:**
  - se controlan por declaración de la persona; una declaración falsa no se detecta;
  - el control por país de la conexión solo funciona si el proxy proporciona una fuente GeoIP, y hoy no está
    configurado;
  - Crimea, Donetsk y Luhansk solo se cubren con la declaración.
- **Audio de reuniones:** AINGEL no puede comprobar que las otras personas estén informadas.
- **Retención en Meta:** no hay retención cero contratada (§4.4 de las condiciones de Meta).
- **Rutinas:** los avisos necesitan la pantalla Hoy abierta. No hay notificaciones push ni alarmas en segundo plano.
- **Salud:** la búsqueda en MedlinePlus es educativa. AINGEL no es un dispositivo médico, no diagnostica, no da
  dosis y no garantiza que un lugar o una ruta sean seguros.
