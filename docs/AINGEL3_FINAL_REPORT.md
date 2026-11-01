# AINGEL 3.0 · Informe final (31-10-2026)

**Estado:** las seis fases están construidas y probadas en sus PR, ninguna está fusionada ni desplegada, y no se tocó
el VPS. Este documento resume las seis fases. El detalle de cada una está en `docs/AINGEL3_PHASE1_DEEP_VISION.md` …
`docs/AINGEL3_PHASE6_INSTALLER.md`.

## 1. PR y orden de fusión

Los PR están apilados: cada uno contiene al anterior. Hay que fusionarlos **en este orden**.

| Orden | PR | Contenido |
|---|---|---|
| 1 | #4 | Arreglos de Android: mensaje de cámara, ojos de AINGEL, voz sin paquete de idioma |
| 2 | #5 | Reconocimiento experimental de señas por cámara; «tú» apunta a quien mira |
| 3 | #6 | **Fase 1:** visión profunda, prompt maestro versionado, registro de consumo de Meta |
| 4 | #7 | **Fase 2:** AINGEL Desktop para Windows |
| 5 | #8 | **Fase 3:** documentos y libros (PDF, escaneados, navegación, explicación) |
| 6 | #9 | **Fase 4:** subtítulos del audio del equipo (WASAPI) |
| 7 | #10 | **Fase 5:** registro de señas validadas; solo señas validadas por defecto |
| 8 | #11 | **Fase 6:** instalador de Windows y sección «AINGEL para tu computadora» |

## 2. Qué se entregó

- **Motor de Meta (fase 1):**
  - prompt maestro versionado (`2026-10-31`), con identidad y 13 políticas;
  - cuatro niveles de detalle, con esfuerzo y presupuesto que dejan sitio al razonamiento;
  - modo profundo en 3 llamadas (global, regiones ampliadas, síntesis);
  - siete tareas visuales (rostro, dibujo, académico, documento, gráfico, pantalla, general);
  - zonas con recorte y texto sin Markdown para la voz;
  - las instrucciones viajan en el campo `instructions` de la API (fase 3).
- **Seguimientos multimodales:**
  - Las preguntas sobre la misma imagen o documento usan una sesión cifrada, que dura 15 min para imágenes y 2 h para
    documentos.
  - Se vuelve a comprobar el consentimiento en cada uso. Una revocación borra la sesión.
- **Consumo:** el registro `MetaUsage` guarda tokens, latencia y coste, sin contenido. Con
  `AINGEL_META_BUDGET_USD`, el presupuesto detiene las llamadas al alcanzarse. Resumen con `manage.py meta_usage`.
- **AINGEL Desktop (fases 2, 3, 4 y 6):** WPF con .NET 8, sin paquetes NuGet.
  - Inicio de sesión con segundo factor y sesión cifrada con DPAPI.
  - **Pantalla:** captura bajo demanda de la ventana o la pantalla, sin capturarse a sí misma y sin evitar el DRM.
  - **Foco:** lectura local con UI Automation, sin leer contraseñas.
  - **Documentos y subtítulos:** lector de documentos y subtítulos *loopback*.
  - **Uso:** 9 atajos Ctrl+Alt y voz SAPI que se calla si hay un lector de pantalla.
  - **Distribución:** instalador por usuario y aviso de versiones nuevas.
- **Documentos (fase 3):**
  - Lectura exacta del texto del PDF, sin llamar a Meta.
  - Índice de capítulos y búsqueda.
  - Transcripción con IA de las páginas escaneadas, a petición.
  - Explicar, resumir, describir figuras y responder preguntas con el documento como única fuente.
- **Señas (fase 5):**
  - Registro con fuente, licencia, variante regional y estado.
  - Validación ligada a la huella exacta de cada animación.
  - **Por defecto, solo señas validadas.** Hoy no hay ninguna, así que se muestra el texto completo con aviso.
  - Los diseños de AINGEL solo se ven como «ilustrativos», si se eligen.
  - Correcciones de personas que signan.
- **Web:** visión con niveles y seguimientos, lector de documentos, traductor de señas con el registro y la sección
  «AINGEL para tu computadora».
- **Android:** visión profunda con seguimientos y los botones «Más detalle» y «Explorar a fondo», voz por partes y
  traductor de señas con el registro.

## 3. Criterios de entrega del pliego (§28)

| # | Criterio | Estado |
|---|---|---|
| 1 | Backend | ✅ |
| 2 | Android | ✅ Visión profunda, seguimientos y registro de señas. ⚠️ Todavía no abre PDF ni envía correcciones de señas. |
| 3 | Web | ✅ |
| 4 | Código de AINGEL Desktop | ✅ `desktop/` |
| 5 | Captura de pantalla y audio | ✅ Probadas en este Windows. |
| 6 | Motor de descripción profunda | ✅ |
| 7 | Libros y documentos | ✅ En la web y el escritorio. |
| 8 | Subtítulos de reuniones | ✅ En el escritorio. ⚠️ Las reuniones con terceros esperan tu decisión (§8). |
| 9 | Señas validadas o estado parcial explícito | ✅ Estado explícito: 0 de 81 validadas. |
| 10 | Prompt de Meta versionado | ✅ |
| 11 | Pruebas automatizadas | ✅ Ver §4. |
| 12 | Resultados reales | ✅ Ver §5. |
| 13 | Instrucciones de compilación | ✅ `desktop/README.md` y los documentos de cada fase. |
| 14 | Instalador verificado | ✅ Instalar, abrir, actualizar y desinstalar se probaron de verdad en este Windows. ⚠️ No está firmado. |
| 15 | Botón de descarga | ✅ Integrado. Solo aparece con un instalador publicado y verificado; no se publicó ningún enlace. |
| 16 | Arquitectura, seguridad y accesibilidad | ✅ En los documentos de cada fase y en este informe. |
| 17 | Despliegue y reversión | ✅ Ver §7. |
| 18 | Limitaciones y siguiente trabajo | ✅ Ver §9. |

## 4. Pruebas automatizadas (último estado)

| Parte | Resultado |
|---|---|
| Backend (`manage.py test`) | **280 correctas**, 6 omitidas (necesitan Redis real; las ejecuta Astra) |
| Web | `typecheck`, `build` y 8 pruebas: `vision`, `documents`, `sign-registry`, `desktop-download`, `private-media`, `synthetic-conversation`, `browser-speech` y `revocation`. Todas correctas. |
| Android | Compilación, **82 pruebas unitarias** correctas y 0 errores de lint |
| Escritorio | **96 comprobaciones** locales correctas, más otras contra un backend local: la API, los documentos y, en un modo aparte, la prueba G |

## 5. Pruebas funcionales del pliego (§25)

Todas las pruebas con Meta usaron **solo material sintético dibujado por el servidor o voz sintética de Windows**. No
se envió nada de personas reales.

| Prueba | Resultado |
|---|---|
| **A. Rostro** | ✅ Con un retrato ilustrado ficticio: rasgos completos (forma, frente, cejas, ojos e iris, lentes, nariz, boca, orejas). No atribuye identidad, etnia ni emociones. ⏳ Sin probar con un rostro real: requiere tu prueba privada. |
| **B. Dibujo reconocible** | ✅ «Veo un perro». Luego describe partes, trazos, relleno y composición. |
| **C. Dibujo ambiguo** | ✅ Reconoce la duda. En modo académico solo da observaciones y ningún diagnóstico. |
| **D. Libro en PDF** | ✅ Lectura exacta (une «jar-dín»), capítulos, búsqueda, figura con sus valores, explicación separada de la lectura y resumen fiel. |
| **E. PDF escaneado** | ✅ Transcripción palabra por palabra. El gráfico se describe en español con los valores exactos, después de corregir el envío de instrucciones. |
| **F. Pantalla de Windows** | ✅ Con una pantalla sintética, desde el escritorio: estándar en 7,7 s y a fondo en 26,8 s. ⏳ Pantalla real sin probar. |
| **G. Reunión** | ✅ Reunión ficticia leída por la voz de Windows: transcripción exacta. ⏳ Reunión real sin probar (§8). |
| **H. Señas** | ✅ Registro, regla de validación, huellas y bloqueo de lo no validado, con pruebas en las tres plataformas y en el navegador. |
| **I. Revocación** | ✅ Pruebas automáticas: la revocación borra las sesiones de imagen y los documentos, descarta la respuesta si ocurre durante la llamada, y los subtítulos se detienen. |
| **J. Presupuesto de Meta** | ✅ Registro y tope probados. Gasto en vivo registrado: **0,37 USD**, 25 llamadas; no incluye la transcripción de voz, que no informa tokens. |
| **K. Multiplataforma** | ✅ Misma cuenta, servidor y reglas en la web, Android y el escritorio. ⏳ Las funciones 3.0 de Android no se probaron en el teléfono: falta desplegar. |
| **L. NVDA y teclado** | ⚠️ Todo se probó con UI Automation, que es lo que lee NVDA: nombres, avisos en vivo y manejo por teclado. NVDA no está instalado en este equipo, así que **no se probó con NVDA**. |

**Errores reales encontrados al probar y corregidos:**
1. **Fase 1:**
   - El primer seguimiento no tenía el turno inicial.
   - Una pregunta escrita podía ir junto a una imagen sintética; ahora se rechaza.
2. **Fase 2:**
   - Los campos no tenían nombre accesible.
   - La captura fallaba siempre.
   - Las casillas no respondían a la acción Alternar.
3. **Fase 3:** Meta respondió «Hey there! I'm Muse Spark» a una página que solo tenía un gráfico. Ahora las
   instrucciones van en el campo `instructions`.
4. **Fase 4:** el final de cada turno llega vacío desde Meta y no se mostraba nada.
5. **Fase 5:** el formulario de corrección empezaba sin seña elegida.
6. **Fase 6:**
   - Sin carpeta de escritorio, la instalación fallaba.
   - Había un botón con el texto cortado.
   - El manifiesto se escribía con BOM.

## 6. Arquitectura, seguridad y accesibilidad (resumen)

- **Arquitectura:**
  - Un solo backend (Django/DRF/Channels) para la web, Android y el escritorio, con las mismas cuentas, el mismo CSRF
    y los mismos permisos.
  - Módulos nuevos: `assistance/vision.py`, `documents.py`, `sealed.py`, `usage.py`, `care/sign_registry.py`.
  - El escritorio usa la misma API y el mismo WebSocket de subtítulos.
- **Seguridad y privacidad:**
  - **Datos que se guardan:** `store=false` con Meta. Las imágenes y documentos solo existen como sesiones cifradas
    con caducidad. El registro de consumo no guarda contenido. El material sintético no admite texto libre.
  - **Comprobaciones:**
    - Los permisos se vuelven a comprobar en cada llamada.
    - No se reactivó el reconocimiento facial.
    - Las protecciones del modo privado siguen igual.
  - **Escritorio:**
    - Captura solo a petición y sin capturarse a sí mismo.
    - Respeta el DRM.
    - No lee contraseñas.
    - No guarda las transcripciones.
  - **Instalador:**
    - Funciona sin administrador.
    - Comprueba el SHA-256 y bloquea entradas del zip que apunten fuera de su carpeta.
    - No tiene modo silencioso.
- **Accesibilidad:**
  - Todos los controles del escritorio tienen nombre, verificado con UI Automation.
  - Hay regiones en vivo, foco visible y manejo completo por teclado.
  - La voz no se superpone al lector de pantalla.
  - Las respuestas no llevan Markdown y la voz lee el texto por partes.
  - En la web, el texto completo se muestra cuando no hay señas validadas.

## 7. Despliegue (Astra) y reversión

**Despliegue, después de fusionar los PR en orden:**

1. **Backend:**
   - Reconstruir la imagen, porque hay dependencias nuevas que autorizaste: `pypdf` 6.21.4 y `pypdfium2` 4.30.0.
   - Ejecutar `migrate`: `assistance.0001` (consumo) y `care.0009` (correcciones de señas).
2. **Variables y proxy:**
   - Opcional: `AINGEL_META_BUDGET_USD`.
   - Si hay una CDN o un proxy con límites, permitir 180 s en `/api/v1/vision/` y 21 MB en `POST /api/v1/documents/`.
   - `AINGEL_WEBSOCKET_ORIGINS` debe incluir el origen del sitio, igual que para la web.
3. **Clientes:** compilar la web y la APK nuevas.
4. **Descarga de Windows**, solo cuando decidas publicarla:
   1. Ejecutar `desktop\Build-Installer.ps1` en Windows.
   2. Entregar el instalador y `manifest.json`.
   3. Astra los coloca en `downloads/` del sitio y comprueba el SHA-256.
5. **Ajustes de producción:** no hay cambios de permisos ni de tratamiento de datos que se activen solos. Los
   interruptores de producción siguen como están.

**Reversión:**
- Revertir los commits.
- Las sesiones en caché caducan solas.
- `migrate assistance zero` y `migrate care 0008` quitan solo las tablas nuevas; exporta antes las correcciones.
- La aplicación se desinstala desde Configuración › Aplicaciones.

## 8. Decisiones que te corresponden

1. **Reuniones con otras personas:** la prueba privada actual es solo para audio propio. Para subtitular reuniones
   reales hay que activar los permisos normales de voz (`AINGEL_REAL_DATA`), y los participantes deben saberlo.
2. **Permisos propios para pantalla y documentos:** hoy usan los permisos de imágenes. Separarlos es un cambio del
   modelo de consentimiento.
3. **Firma de código:** hace falta un certificado. Sin él, SmartScreen avisará.
4. **Escritorio sin el runtime de .NET:** una versión autocontenida, o una con `Windows.Graphics.Capture` y WebView2,
   necesita tu permiso para descargar paquetes de Microsoft.
5. **Señas ilustrativas por defecto:** hoy están desactivadas, como pide el pliego. Puedes pedir otro
   comportamiento.

## 9. Limitaciones y siguiente trabajo recomendado

**Imprescindible antes de declarar terminadas las funciones:**
- **Validar señas con personas sordas usuarias de LSEC:** sin eso no hay interpretación en señas.
- **Probar con NVDA, JAWS y Narrador** en el escritorio y la web.
- **Desplegar y hacer la prueba privada con tu propio material:** rostro real, tu pantalla y fotos en el teléfono.

**Siguiente trabajo:**
1. **Android:**
   - abrir PDF con el selector de documentos;
   - formulario de correcciones de señas.
2. **Escritorio:**
   - traductor de señas, que hoy solo está en la web y Android;
   - control por voz, cuyos comandos (§17) aún no existen.
3. **Rendimiento:** el modo profundo tarda alrededor de un minuto. Se puede medir con imágenes reales y ajustar sin
   perder calidad.
4. **Distribución:** probar en un Windows 10 físico y en ARM64, y probar en un equipo sin el .NET 8 Desktop Runtime.
5. **Varios hablantes:** verificar la separación de voces en los subtítulos.
