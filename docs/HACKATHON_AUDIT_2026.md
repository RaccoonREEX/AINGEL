# Auditoría del hackathon de Meta para AINGEL

## Actualización del 2-11-2026 (rama `release/hackathon-submission-2026`)

### Reglas oficiales releídas

Fuente: la página pública de [Official Rules y waiver](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver),
releída el 2-11-2026. Esto no es asesoría legal.

- **Licencia del código:** las reglas no exigen una licencia de código abierto.
  - Permiten incluir software de código abierto si se respetan sus licencias y la entrega lo mejora.
  - El requisito de repositorio público procede de la guía del participante y se cumple con un repositorio público
    bajo licencia propietaria.
- **Titularidad:** el participante conserva la titularidad de la entrega.
- **Licencia a los organizadores, al presentar:** perpetua, irrevocable, mundial, sin regalías y no exclusiva, para
  usar, reproducir, adaptar, publicar, distribuir y crear obras derivadas «para cualquier fin». `LICENSE` declara
  que no restringe esa concesión. Los «Materials» compartidos en el evento tampoco son confidenciales.
- **Garantías del participante:**
  - la entrega es obra propia;
  - es de su propiedad exclusiva;
  - no infringe derechos de terceros.

  Se permite contratar asistencia técnica de terceros si los componentes siguen siendo obra y propiedad del
  participante. AINGEL se desarrolló con asistentes de programación de IA bajo la dirección del propietario, lo que
  se declara en el README. **El propietario debe confirmar que esto encaja con su garantía.**
- **Criterios:** impacto 30 %, uso de herramientas de Meta 25 %, profundidad técnica 20 %, demo 25 %. Dos tracks;
  una entrega entra en un solo track.
- **Elegibilidad:** 18 años o más, mayoría de edad local y no estar en jurisdicciones excluidas. La confirmación
  personal sigue pendiente del participante.

### Estado de lo pendiente en la versión del 29-10-2026

| Asunto | Estado al 2-11-2026 |
|---|---|
| Barrera de edad en el producto | Hecha: autodeclaración 18+ obligatoria en el registro y bloqueo de Meta sin ella |
| Territorios restringidos de Meta | Hechos: declaración en el registro y en cuentas existentes, bloqueo en el servidor y control opcional por país |
| Modalidad de Meta | Solo modelos Standard; una prueba impide los Contributor |
| Despliegue y demo | Producción en <https://aingel.mapatechstudio.com> (HTTPS y salud comprobados el 2-11-2026) |
| Licencia propia | Borrador propietario en `LICENSE`, pendiente de aprobación |
| Avisos de terceros | Actualizados (Desktop, nota propietaria). Ver `THIRD_PARTY_NOTICES.md` |
| Repositorio público limpio | Auditoría del 2-11-2026 en `PUBLICATION_READINESS.md`: sin secretos. Decisiones pendientes del propietario: identidades de commits y documentos internos |
| Track y tema | Planificado: Indie Developer / Build for Your World. **Confirmar con la inscripción real** |
| Vídeo de tres minutos | Pendiente (previsto para el 2-11-2026) |
| Envío del formulario | No realizado; no se aceptaron términos en nombre del propietario |

### Pruebas sobre la rama final

Ver «Resultados de pruebas» al final de este documento.

---

## Versión del 29-10-2026, conservada como historial

## Auditoría del hackathon de Meta para AINGEL — 29 de octubre de 2026

**Estado:** revisión de fuentes oficiales y documentación local; no es una determinación de elegibilidad ni una auditoría legal. Las reglas pueden cambiar. La guía y el formulario se consultaron con una sesión autenticada; sus enlaces pueden requerir inicio de sesión. No se modificó ni envió el formulario.

## Concurso y calendario verificados

- El evento es el [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon), virtual, de Meta y Cerebral Valley. La presentación vence el **4 de noviembre de 2026 a las 21:00 ET/EST**, que ese día es **21:00 en Ecuador continental (America/Guayaquil)** y el 5 de noviembre a las 02:00 UTC. Reconfirmar antes del envío: el organizador puede cambiar fechas.
- La [guía del participante](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details) indica que el 3 de noviembre es el último día completo para preguntas y asistencia técnica; el objetivo interno de entrega del 3 de noviembre es una decisión del proyecto, no la fecha oficial.
- Las [reglas oficiales y waiver](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver) requieren solicitud individual y aceptación, 18 años y mayoría de edad local, cumplimiento de restricciones geográficas, sanciones y afiliaciones. Incluyen exclusiones para personal de Meta y Cerebral Valley, personas afiliadas al gobierno y ciertas familias y convivientes. La elegibilidad personal y la aceptación deben verificarse con la confirmación privada del participante; acceso a la guía no las demuestra.

## Reglas y evaluación de AINGEL

| Tema | Verificado en reglas y comparación con el proyecto | Pendiente o incierto |
| --- | --- | --- |
| Track y equipo | Un proyecto entra en un track. Indie admite personas y equipos de hasta cuatro; Startup exige representante empleado activo y autorizado. La guía permite trabajar solo. | El formulario consultado muestra ambas opciones sin seleccionar; esto no identifica el track de la solicitud original. Confirmar aceptación, track, integrantes y representante. Indie / Build for Your World es una hipótesis de planificación, no una inscripción verificada. |
| Trabajo nuevo | La demo debe destacar solamente funciones, código y comportamiento creados durante el hackathon, identificados claramente. La guía permite expresamente a startups partir de un producto o código previo si distinguen lo nuevo. | Preparar una cronología y evidencia de procedencia y fechas del código, recursos y aportes; identificar cualquier trabajo previo. No asumir que la excepción explícita para startups se aplica igualmente a Indie; consultar al organizador si es relevante. |
| Meta y valoración | La guía exige incorporar modelos Meta y superar un filtro inicial de ajuste al tema y uso razonable de Meta Model API o modelos abiertos de Meta. Rúbrica: impacto 30 %, uso de herramientas Meta 25 %, ingeniería 20 %, demo 25 %. | README y resultados locales documentan llamadas sintéticas reales a Spark, SAM y Voice, pero no prueban calidad general ni que toda función esté lista. Mostrar una secuencia reproducible y atribuir cada salida correctamente. |
| Alcance y salud | La guía enumera como ejemplos que deben evitarse proyectos de IA que generen o den consejo médico, RAG básico y analizadores de imágenes simples. El alcance documentado de AINGEL excluye diagnóstico y dosificación; describe búsqueda educativa de MedlinePlus con atribución y funciones de apoyo. | Revisar salidas, textos, vídeo y casos de prueba para evitar consejo médico o afirmaciones clínicas. La exclusión en el documento no demuestra por sí sola que todas las respuestas generadas cumplan. La decisión de los jueces no está garantizada; demostrar el flujo integrado, no solo un analizador aislado. |
| Repositorio y demo | La guía exige repositorio público, vídeo accesible de tres minutos, participantes listados y un representante que envíe un solo proyecto por equipo. Jueces consideran vídeo, código y producto en vivo. | Se creó el repositorio privado [RaccoonREEX/AINGEL](https://github.com/RaccoonREEX/AINGEL); su carácter privado no satisface el requisito de entrega pública. La documentación describe una APK debug y pruebas locales; el despliegue y las pruebas integrales aún están pendientes. Falta verificar un repositorio público limpio, vídeo accesible, demo funcional y forma de acceso del jurado. Una APK no es un requisito explícito hallado en la guía. |
| Entrega | El [formulario](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit) pide nombre/equipo, track, tema, descripción, GitHub público, vídeo, uso e importancia de Meta, feedback de socios y opiniones sobre Model API; contiene una casilla de permiso promocional. | En la vista consultada los campos y selecciones estaban vacíos; esa vista no demuestra ni descarta un envío previo. Confirmar estado y conservar comprobante si se presenta. Revisar la casilla y términos antes de actuar. |

## Derechos, privacidad y condiciones de IA

- **Derechos de la entrega:** el participante conserva la titularidad frente al organizador, pero concede una licencia de explotación amplia, mundial, perpetua, irrevocable y sin regalías. Los materiales compartidos en el evento no se consideran confidenciales. Las reglas admiten asistencia técnica de terceros y componentes de código abierto si se cumplen sus condiciones y la entrega los mejora; no mencionan expresamente herramientas concretas de asistencia por IA. Revisar titularidad, contribuciones, permisos y términos de las herramientas usadas; no inferir autorización ilimitada.
- **Datasets y licencias:** [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [THIRD_PARTY_INVENTORY.md](THIRD_PARTY_INVENTORY.md) y [DATASET_RESEARCH.md](DATASET_RESEARCH.md) documentan fuentes y asuntos abiertos. Se reportan 30 anotaciones VizWiz para evaluación local, sin imágenes ni entrenamiento; dos clips LSEC para investigación, no activados; MedlinePlus atribuido; y parser SAM bajo SAM License. Confirmar exactamente qué archivos se distribuyen y sus derechos/atribuciones, revisar licencias transitivas y avisos del APK, metadatos pendientes y derechos de imagen. La licencia propia del proyecto sigue por decidir; un repositorio público no implica por sí solo una licencia de software determinada. Los documentos locales tienen fechas y alcances distintos: verificar el estado real antes de publicar.
- **Menores y Model API:** los [términos de Meta Model API, sección 10.1](https://dev.meta.ai/legal/terms-of-service), indican que usuario y usuarios finales deben tener al menos 18 años y que no se deben crear productos integrados dirigidos a menores de 18. Esto es separado de la edad para participar en el hackathon. No se verificó aquí una barrera de edad eficaz en AINGEL; antes de usar o presentar el producto integrado con usuarios reales, revisar su público y controles aplicables. No afirmar que los términos permiten uso por menores sin una autorización aplicable de Meta.
- **Datos y servicios:** según los [términos de Meta](https://dev.meta.ai/legal/terms-of-service), Standard no usa el contenido de las solicitudes para entrenar modelos; Contributor prohíbe enviar información personal, sensible o confidencial y tiene condiciones distintas. La documentación de AINGEL mantiene pendiente conciliar el aviso de créditos gratuitos con el tratamiento de datos reales. Confirmar modalidad efectiva, condiciones de créditos, política de privacidad y derechos de las entradas antes de usar datos personales; para la demo usar material sintético. Las afirmaciones de `synthetic` dependen de la persona y no detectan contenido sensible.
- La [política de uso aceptable de Meta](https://dev.meta.ai/legal/acceptable-use-policy) impone restricciones sobre privacidad, biometría, vigilancia y decisiones sobre salud o seguridad sin revisión cualificada. El reconocimiento familiar documentado es local y experimental, con consentimiento y sin garantías de precisión; esto no acredita cumplimiento legal completo. Revisar alcance, base legal, consentimiento, riesgos y limitaciones antes de mostrar o usar datos de personas reales.

## Preparación pendiente antes de una presentación

1. Confirmar aceptación, elegibilidad, track, equipo y términos efectivamente aplicables; aclarar con el organizador cualquier duda sobre trabajo previo o asistencia de IA.
2. Documentar y seleccionar aportes creados durante el evento; revisar derechos y atribuciones de código, modelos, datasets, imágenes, audio y personas. Preparar un repositorio público sin secretos, datos privados ni archivos ajenos sin autorización.
3. Grabar y probar un vídeo de tres minutos, y verificar acceso del jurado al código y a una demo funcional. Distinguir pruebas sintéticas, capacidades verificadas y limitaciones; no prometer precisión facial, traducción validada de señas ni otras funciones no demostradas.
4. Completar el formulario con descripciones y feedback veraces, revisar la autorización promocional y obtener una confirmación de envío antes del plazo. Este informe no constituye presentación ni aceptación de condiciones.
