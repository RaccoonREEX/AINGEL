# AINGEL 3.0 · Fase 6: instalador de Windows y sección de descarga (31-10-2026)

Rama `feat/aingel3-installer`, apilada sobre `feat/aingel3-validated-signs` (PR #10). No está fusionada ni
desplegada, y **no se publicó ningún enlace de descarga**.

## Instalador (`desktop/AingelSetup`, `desktop/Build-Installer.ps1`)

Inno Setup, WiX y la firma de MSIX necesitan descargas o cambios en el sistema. Por eso el instalador es un programa
WPF propio, hecho solo con lo que trae .NET, sin paquetes NuGet:

| Requisito del pliego (§20) | Cómo se cumple |
|---|---|
| Instalación guiada y accesible | Asistente de cuatro pasos: qué se instala y dónde, requisitos, instalación y fin. Se maneja con teclado, todos los controles tienen nombre y cada paso se anuncia como región en vivo. |
| Detección de requisitos | Windows 10 2004 o posterior (para excluir su propia ventana de las capturas), 50 MB libres, AINGEL abierto. Si falta el .NET 8 Desktop Runtime, Windows lo avisa al abrir el instalador y ofrece el enlace oficial de Microsoft. |
| Por usuario, sin administrador; UAC solo si hace falta | `asInvoker`: ninguna función necesita elevación. Se instala en `%LOCALAPPDATA%\Programs\AINGEL Desktop`. |
| Accesos directos y menú Inicio | Siempre en el menú Inicio; en el escritorio, si se elige. |
| Desinstalador | Aparece en Configuración › Aplicaciones (HKCU). Continúa desde una copia temporal visible y pregunta si también se borran las preferencias. Por defecto las conserva. |
| Editor y versión | Mapatech Studio, en la entrada de Configuración y en el asistente. |
| Registro de instalación sin secretos | `%LOCALAPPDATA%\AINGEL\install.log` recoge pasos y rutas. Nunca guarda contraseñas ni sesiones. |
| Verificación SHA-256 | Doble: el instalador comprueba su contenido contra una huella interna antes de escribir, y la página publica la huella del instalador con el comando para comprobarla. |
| Firma de código | **No firmado**: no hay certificado. La página y el asistente lo dicen y explican cómo comprobar la huella. SmartScreen puede avisar, y no se desactiva nada. |
| Actualización segura | La aplicación consulta `downloads/manifest.json` del mismo servidor y **solo avisa** si hay una versión nueva. Nunca descarga ni ejecuta nada por su cuenta. |
| Nueva versión sin perder preferencias | Se reemplazan solo los archivos del programa. Las preferencias y la sesión están en `%LOCALAPPDATA%\AINGEL\Desktop`. |
| Sin instalación silenciosa ni servicios | No existe modo silencioso. No instala servicios ni inicio automático. |

**Comando:** `Build-Installer.ps1` publica la aplicación, la comprime, incrusta el zip y su huella, publica el
instalador como un solo archivo y escribe `manifest.json`. Con `-Web`, copia ambos en `web/public/downloads`.

**Resultado aquí:**

| Dato | Valor |
|---|---|
| Archivo | `AINGEL-Desktop-Setup-0.1.0.exe` |
| Tamaño | 333 404 bytes |
| SHA-256 | `9df10d116e851b87836ddb6ec34c6b07655722a4a0010f1400034c02a9f1eaed` |
| Compilación | Reproducible: dos compilaciones dieron el mismo SHA-256 |

## Pruebas reales en este Windows (Windows 11 Pro for Workstations)

Manejadas con UI Automation, con el **instalador final** (SHA-256 `9df10d11…`):

1. **Instalar:**
   - asistente con controles nombrados;
   - archivos en `%LOCALAPPDATA%\Programs\AINGEL Desktop`;
   - acceso del menú Inicio apuntando a `AingelDesktop.exe`;
   - entrada en Configuración › Aplicaciones: «AINGEL Desktop 0.1.0 · Mapatech Studio», con el comando de
     desinstalación.
2. **Abrir:** la aplicación instalada abre su ventana para entrar.
3. **Actualizar:** al instalar encima, el asistente muestra «Actualizar» y las preferencias se conservan.
4. **Desinstalar:** con el comando registrado, se borran la carpeta, el acceso y la entrada de Configuración. Las
   preferencias se conservan, porque es la opción por defecto.
5. **Limpieza:** el equipo quedó como estaba. No queda carpeta, entrada en el registro ni datos de prueba.

**Comprobaciones automáticas:** 96 en `AingelDesktop.Tests`. Las 17 del instalador comprueban:
- los requisitos;
- un paquete sin la aplicación;
- una entrada del zip que apunta fuera de la carpeta;
- la instalación, los accesos directos y el registro;
- la actualización, que conserva las preferencias;
- un registro sin secretos;
- la desinstalación, conservando o borrando las preferencias.

**Errores encontrados y corregidos:**
1. **Acceso directo del escritorio:** si la carpeta del escritorio no existía, la instalación entera fallaba. Ahora
   el acceso del escritorio es opcional y no bloquea.
2. **Botón cortado:** la captura de la ventana principal mostró cortado «Abrir documento PDF o foto de página
   (Ctrl+Alt…». Ahora los textos de los botones se ajustan, sin cambiar el nombre accesible.
3. **Manifiesto con BOM:** se escribía con BOM; ahora va en UTF-8 sin BOM.

## Sección web «AINGEL para tu computadora» (§19)

Está en el menú de la cuenta y en «Más», en `web/src/components/DesktopDownload.tsx`, y contiene:
- qué hace;
- tres **capturas reales**: ventanas dibujadas por el propio código de la aplicación, sin datos de nadie, generadas
  con `AingelDesktop.Tests --screenshots`;
- compatibilidad y requisitos;
- privacidad y permisos del sistema;
- manual de instalación accesible;
- comprobación de integridad con `Get-FileHash`;
- desinstalación;
- versión y fecha.

El botón **«Descargar AINGEL para Windows» aparece solo si existe `/downloads/manifest.json`** con un archivo y su
SHA-256 válidos. Si no, la página dice que el instalador aún no está publicado y no muestra ningún enlace.

**Comprobado en el navegador:**
- **Con el instalador local:** el botón descarga el archivo real, y su SHA-256, calculado en el navegador sobre lo
  descargado, es exactamente el publicado.
- **Sin él:** aparece el aviso honesto, sin enlaces.

**Prueba automática:** `test:desktop-download` rechaza manifiestos sin huella, con URL externas o con rutas fuera de
`downloads/`.

## Publicar una versión (lo hacen la propietaria o el propietario y Astra)

1. En Windows, ejecutar `desktop\Build-Installer.ps1`. Hace falta el SDK de .NET 8 o posterior.
2. Comprobar los dos archivos de `desktop\dist-installer`: el instalador y `manifest.json`. Opcionalmente, repetir la
   prueba real de instalación.
3. Entregar esos dos archivos a Astra. Astra los coloca en `web/public/downloads/` antes de compilar la web, o en la
   carpeta de descargas que sirve nginx, y comprueba que el SHA-256 coincide.
4. Hasta entonces, la sección muestra el aviso de no publicado. **Este cambio no publica ningún enlace por sí
   mismo**: `web/public/downloads` no está en git.

## Reversión

- **Web:** revertir el commit, o borrar `downloads/` del sitio; el botón desaparece solo.
- **Equipos con la aplicación instalada:** se desinstala desde Configuración › Aplicaciones.

## Límites

- **Firma:** sin firma de código hasta tener un certificado.
- **Dependencia:** depende del .NET 8 Desktop Runtime. La versión autocontenida necesitaría descargar los paquetes de
  runtime de Microsoft, con tu permiso.
- **Arquitectura:** solo x64. No se probó en Windows 10 físico, ni en ARM64, ni con NVDA.
- **Actualizaciones:** solo avisan; no hay actualización automática, a propósito.
