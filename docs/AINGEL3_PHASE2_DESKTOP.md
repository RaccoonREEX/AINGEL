# AINGEL 3.0 · Fase 2: AINGEL Desktop para Windows (31-10-2026)

- **Rama:** `feat/aingel3-desktop`, apilada sobre `feat/aingel3-deep-vision` (PR #6). No está fusionada ni
  desplegada.
- **Uso y compilación:** `desktop/README.md`.

## Qué se construyó

`desktop/AingelDesktop` es una aplicación WPF con .NET 8 que solo usa bibliotecas incluidas en .NET: no tiene
paquetes NuGet y no se descargó nada. Contiene:

- **Inicio de sesión:**
  - Usuario y contraseña; el segundo factor cuando la cuenta lo tiene.
  - Elección de perfil.
  - CSRF y cabecera `Origin` como en Android, con un reintento si falla el CSRF.
  - Sesión cifrada con DPAPI.
  - Servidor configurable: HTTPS, o HTTP solo en loopback.
- **Ventana flotante:**
  - Orbe con tres estados de color y pulso mientras piensa.
  - Botones, nivel de detalle, pregunta y respuesta.
  - Opciones: «Siempre visible», voz, prueba privada y prueba sintética.
- **Siete atajos globales** con Ctrl+Alt: D, P, Q, M, F, S y A.
- **Captura bajo demanda:**
  - De la ventana activa o de su monitor, con GDI `BitBlt` y `CAPTUREBLT`.
  - JPEG de hasta 2048 px.
  - La ventana de AINGEL queda excluida (`WDA_EXCLUDEFROMCAPTURE`).
  - Si la ventana activa es AINGEL, se usa la última ventana usada antes (`SetWinEventHook`). Solo se guarda su
    identificador.
- **Lectura local del foco con UI Automation:** sin red, y nunca el contenido de un campo de contraseña.
- **Voz:** SAPI, el motor de voz de Windows, con una voz del idioma del perfil. Se silencia si hay un lector de
  pantalla y la respuesta se anuncia como región en vivo.
- **Seguimientos:**
  - Las preguntas sobre la misma imagen usan la sesión de la fase 1.
  - «Explorar a fondo» pide el nivel `deep`.
  - Al pedir otra imagen o cerrar sesión, la sesión anterior se borra en el servidor.
- **Backend:** una nueva imagen sintética, `screen_desktop`: una pantalla de Windows ficticia con Bloc de notas, menú
  y un diálogo «Guardar cambios». Además, la política de pantalla ahora dice que los separadores de los títulos se
  leen como pausa, no como «menos».

## Pruebas ejecutadas en este Windows (Windows 11 Pro for Workstations)

- **Compilación:** `dotnet build -c Release` sin errores ni avisos. `Build-Desktop.ps1` compila, comprueba y publica:
  294 KB, dependiente del runtime. SHA-256 de `AingelDesktop.exe`:
  `C80226EA7579890F5042CC76DF0A667D05D98986F76ACE576AA07AC6D26FB34B`.
- **`AingelDesktop.Tests`:** 51 comprobaciones locales correctas:
  - URLs del servidor;
  - campos de visión, incluido que la prueba privada solo vale en el perfil propio y que un fixture no lleva texto;
  - frase del foco, sin leer contraseñas;
  - códigos de error, incluido el CSRF de DRF y de Django;
  - textos y atajos;
  - voces;
  - JPEG a 2048 px;
  - una captura real del monitor, solo en memoria;
  - cookies cifradas, que no se leen si el archivo está dañado y se borran al salir;
  - formulario multipart.
- **Contra el backend local en modo de prueba:** 59 en total. Las 8 de servidor:
  - contraseña errónea rechazada;
  - entrada con CSRF;
  - perfiles;
  - captura descrita;
  - seguimiento;
  - pantalla sintética;
  - texto libre junto a un fixture rechazado;
  - sesión cerrada inexistente y cierre de sesión.
- **La aplicación real, manejada solo con UI Automation:**
  - **Inicio de sesión** y ventana principal: todos los controles tienen nombre.
  - **Ctrl+Alt+F con Bloc de notas:** «Documento «Editor de texto», contiene: Lista de compras: pan, leche y
    manzanas. Ventana: aingel-desktop-check.txt: Bloc de notas.»
  - **Ctrl+Alt+D, y el mismo botón dentro de AINGEL:** la captura llega al servidor (`POST /api/v1/vision/` 200) y la
    sesión anterior se borra (`DELETE` 204).
  - **Exclusión:** una captura del área de la ventana de AINGEL muestra lo que hay detrás, no AINGEL. La imagen se
    borró, porque contenía otras ventanas del equipo.
- **Prueba F, en vivo con Meta y la pantalla sintética:** el servidor local en modo Meta, manejado por la aplicación,
  con 2 llamadas:
  - **Descripción:** 7,7 s. Lee el título, los menús, las cuatro líneas, el diálogo, la casilla, los dos botones, la
    barra de tareas y la hora.
  - **«Explorar a fondo»:** 26,8 s. Más detalle por zonas, con los límites reales: tonos exactos, tamaño en píxeles y
    si las tildes faltan en el original.

### Errores encontrados y corregidos con estas pruebas

1. **Campos sin nombre:** los campos de texto y el selector de nivel no tenían nombre accesible, y NVDA habría dicho
   solo «editar». En WPF, `Label Target` no nombra el control. Corregido con `AutomationProperties.Name`.
2. **La captura fallaba siempre:** `Graphics.CopyFromScreen` rechaza la opción `CaptureBlt`. Ahora se usa `BitBlt`
   directamente, y un fallo de captura se dice en lugar de quedar en silencio.
3. **Casillas ignoradas:** las casillas de opciones no respondían a la acción Alternar de UI Automation (Narrador,
   control por voz), porque no lanza `Click`. Ahora usan `Checked`/`Unchecked`.

## Desviaciones del pliego y por qué

- **WebView2 y `Windows.Graphics.Capture`:** el pliego los pide, pero exigen descargar paquetes NuGet de Microsoft
  (`Microsoft.Web.WebView2` y el paquete de proyecciones de Windows), y no hay permiso para descargar. Se usó WPF
  nativo, más accesible que una web incrustada, y captura GDI, que respeta la exclusión de captura y el DRM. Si
  autorizas esas descargas, se puede cambiar a `Windows.Graphics.Capture`, que además muestra el borde amarillo de
  captura de Windows.
- **Permisos:** las capturas de pantalla usan los permisos de imágenes ya existentes (`camera_local` +
  `meta_photos`). Un permiso propio para «pantalla» es un cambio del modelo de consentimiento que debes decidir tú.
- **NVDA:** no está instalado en este equipo, así que la prueba L se hizo con UI Automation, la interfaz que lee NVDA,
  no con NVDA. Falta probarla con NVDA, JAWS y Narrador.
- **Fases siguientes:** OCR (fase 3), audio del sistema (fase 4) e instalador (fase 6) no están hechos. Inno Setup no
  está instalado. No hay enlace de descarga.

## Despliegue y reversión

- **Despliegue:**
  - El servidor solo necesita la fase 1 desplegada y esta rama, que añade la imagen sintética y una línea del prompt
    de pantalla. No hay migraciones.
  - La aplicación de escritorio no se distribuye todavía.
- **Reversión:** revertir el commit. La aplicación no deja nada en el servidor; en el equipo, «Cerrar sesión» borra
  la sesión, y se puede eliminar `%LOCALAPPDATA%\AINGEL`.

## Límites

- **Entorno:** requiere Windows 10 versión 2004 o posterior para excluir su propia ventana, y el .NET 8 Desktop
  Runtime.
- **DPI:** se declara `PerMonitorV2` y no se probó con varios monitores ni con escalas mixtas.
- **Firma:** no está firmada. Windows SmartScreen puede advertir.
- **Pantalla real:** no se probó con Meta y la pantalla real del propietario. Hace falta el despliegue y la prueba privada.
