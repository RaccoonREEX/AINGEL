import { useEffect, useState } from "react";
import mainShot from "../assets/desktop/desktop-main.png";
import captionsShot from "../assets/desktop/desktop-captions.png";
import signInShot from "../assets/desktop/desktop-sign-in.png";

/** downloads/manifest.json, written by desktop/Build-Installer.ps1 next to the installer it describes. */
export type Release = { product: string; version: string; date: string; file: string; size_bytes: number; sha256: string; signed: boolean; platform: string; requires: string };

/** A release only counts when the manifest names an installer file and its SHA-256: no file, no button. */
export function validRelease(value: unknown): Release | null {
  const release = value as Partial<Release> | null;
  return release && typeof release.file === "string" && /^AINGEL-Desktop-Setup-[\d.]+\.exe$/.test(release.file)
    && typeof release.sha256 === "string" && /^[0-9a-f]{64}$/.test(release.sha256) && typeof release.version === "string"
    ? (release as Release) : null;
}

/**
 * «AINGEL para tu computadora» (AINGEL 3.0 §19): what AINGEL Desktop does, requirements, real screenshots, privacy and
 * system permissions, an accessible installation manual, uninstalling and integrity checking. The download button
 * appears only when a built and verified installer is published next to its manifest; otherwise the page says so.
 */
export default function DesktopDownload({ locale }: { locale: string }) {
  const es = locale === "es-EC";
  const L = (spanish: string, english: string) => (es ? spanish : english);
  const [release, setRelease] = useState<Release | null | undefined>(undefined);
  useEffect(() => {
    fetch("/downloads/manifest.json", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((value) => setRelease(validRelease(value)))
      .catch(() => setRelease(null));
  }, []);
  const megabytes = release ? new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(release.size_bytes / 1048576) : "";
  return (
    <div className="desktop-page">
      <section className="panel">
        <p>{L("AINGEL Desktop es la aplicación de AINGEL para Windows. Usa tu misma cuenta, los mismos permisos y el mismo servidor que la web y el móvil.", "AINGEL Desktop is AINGEL's Windows app. It uses the same account, permissions and server as the web and phone.")}</p>
        {release === undefined ? <p role="status">{L("Comprobando la versión publicada…", "Checking the published version…")}</p>
          : release ? (
            <div className="desktop-download">
              <a className="btn btn-primary btn-pill" href={`/downloads/${release.file}`} download>{L("Descargar AINGEL para Windows", "Download AINGEL for Windows")}</a>
              <p className="hint">{L(`Versión ${release.version} · ${release.date} · ${megabytes} MB · ${release.platform}`, `Version ${release.version} · ${release.date} · ${megabytes} MB · ${release.platform}`)}</p>
              <p className="hint">SHA-256: <code className="sha">{release.sha256}</code></p>
              {!release.signed && <p className="callout">{L("Este instalador aún no está firmado con un certificado de código. Windows SmartScreen puede avisar al abrirlo: comprueba antes su SHA-256 (abajo explicamos cómo) y elige «Más información» › «Ejecutar de todas formas» solo si coincide.", "This installer is not signed with a code-signing certificate yet. Windows SmartScreen may warn when you open it: check its SHA-256 first (explained below) and choose «More info» › «Run anyway» only if it matches.")}</p>}
            </div>
          ) : (
            <p className="callout" role="status">{L("El instalador de Windows aún no está publicado en este sitio. Cuando lo esté, aquí aparecerá el botón «Descargar AINGEL para Windows» con su versión, fecha y huella SHA-256. No publicamos enlaces que no lleven a un instalador real y verificado.", "The Windows installer isn't published on this site yet. When it is, the «Download AINGEL for Windows» button will appear here with its version, date and SHA-256 fingerprint. We don't publish links that don't lead to a real, verified installer.")}</p>
          )}
      </section>

      <section className="panel">
        <h2>{L("Qué hace", "What it does")}</h2>
        <ul>
          <li>{L("Describe la ventana activa o toda la pantalla, con el nivel de detalle que pidas, y responde preguntas sobre ella (Ctrl+Alt+D, Ctrl+Alt+P, Ctrl+Alt+Q, Ctrl+Alt+M).", "Describes the active window or the whole screen, at the level of detail you ask, and answers questions about it (Ctrl+Alt+D, Ctrl+Alt+P, Ctrl+Alt+Q, Ctrl+Alt+M).")}</li>
          <li>{L("Lee el control que tiene el foco, sin enviar nada (Ctrl+Alt+F).", "Reads the focused control, sending nothing (Ctrl+Alt+F).")}</li>
          <li>{L("Abre PDF y fotos de páginas: lectura exacta, capítulos, búsqueda, transcripción de páginas escaneadas y explicaciones (Ctrl+Alt+O).", "Opens PDFs and page photos: exact reading, chapters, search, transcription of scanned pages and explanations (Ctrl+Alt+O).")}</li>
          <li>{L("Subtitula el audio que reproduce el equipo, por ejemplo una reunión o un vídeo (Ctrl+Alt+C).", "Captions the audio the computer plays, such as a meeting or a video (Ctrl+Alt+C).")}</li>
          <li>{L("Funciona con teclado y lectores de pantalla (NVDA, JAWS, Narrador): todos los controles tienen nombre y las respuestas se anuncian.", "Works with the keyboard and screen readers (NVDA, JAWS, Narrator): every control is named and answers are announced.")}</li>
        </ul>
      </section>

      <section className="panel">
        <h2>{L("Capturas reales", "Real screenshots")}</h2>
        <p className="hint">{L("Ventanas de AINGEL Desktop 0.1.0 dibujadas por su propio código, sin datos de nadie.", "AINGEL Desktop 0.1.0 windows drawn by its own code, with nobody's data.")}</p>
        <div className="desktop-shots">
          <figure><img src={mainShot} alt={L("Ventana principal: el orbe de AINGEL, botones con sus atajos (describir ventana, pantalla completa, explorar a fondo, leer elemento con foco, detener voz, abrir documento, subtítulos), nivel de detalle, pregunta y respuesta.", "Main window: AINGEL's orb, buttons with their shortcuts (describe window, whole screen, explore in depth, read focused element, stop speaking, open document, captions), level of detail, question and answer.")} /><figcaption>{L("Ventana principal", "Main window")}</figcaption></figure>
          <figure><img src={captionsShot} alt={L("Ventana de subtítulos detenida: empezar y detener, tamaño de letra, anunciar al lector de pantalla y la transcripción.", "Captions window, stopped: start and stop, text size, announce to the screen reader and the transcript.")} /><figcaption>{L("Subtítulos del audio del equipo", "Captions of the computer's audio")}</figcaption></figure>
          <figure><img src={signInShot} alt={L("Ventana para entrar con usuario y contraseña.", "Sign-in window with username and password.")} /><figcaption>{L("Entrar con tu cuenta", "Sign in with your account")}</figcaption></figure>
        </div>
      </section>

      <section className="panel">
        <h2>{L("Compatibilidad y requisitos mínimos", "Compatibility and minimum requirements")}</h2>
        <ul>
          <li>{L("Windows 10 versión 2004 o posterior, o Windows 11, de 64 bits (x64).", "Windows 10 version 2004 or later, or Windows 11, 64-bit (x64).")}</li>
          <li>{L("El entorno «.NET 8 Desktop Runtime» de Microsoft. Si falta, Windows lo indica al abrir el instalador y ofrece el enlace oficial de Microsoft.", "Microsoft's «.NET 8 Desktop Runtime». If it's missing, Windows says so when the installer opens and offers Microsoft's official link.")}</li>
          <li>{L("50 MB libres, conexión a internet y una cuenta de AINGEL.", "50 MB free, an internet connection and an AINGEL account.")}</li>
        </ul>
      </section>

      <section className="panel">
        <h2>{L("Privacidad y permisos del sistema", "Privacy and system permissions")}</h2>
        <ul>
          <li>{L("Se instala solo para tu usuario, sin permisos de administrador, sin servicios y sin arrancar solo.", "It installs for your user only, without administrator rights, without services and without starting on its own.")}</li>
          <li>{L("Captura la pantalla o el audio solo cuando lo pides; nunca en segundo plano ni en secreto. Su propia ventana no aparece en las capturas, y el contenido protegido (DRM) sale en negro: AINGEL no lo evita.", "It captures the screen or audio only when you ask; never in the background or secretly. Its own window doesn't appear in captures, and protected content (DRM) comes out black: AINGEL doesn't get around that.")}</li>
          <li>{L("Lo capturado va al servidor de AINGEL y a Meta, con tus permisos de imágenes o de voz, que el servidor comprueba siempre. Para tus preguntas de seguimiento el servidor guarda la imagen cifrada hasta 15 minutos y los documentos hasta 2 horas, y luego los borra.", "What is captured goes to the AINGEL server and to Meta, under your image or voice permissions, which the server always checks. For follow-up questions the server keeps the image encrypted for up to 15 minutes and documents for up to 2 hours, then deletes them.")}</li>
          <li>{L("Las transcripciones de subtítulos solo se muestran; no se guardan. Si se oyen otras personas, deben saberlo y aceptarlo.", "Caption transcripts are only shown; they're not saved. If other people can be heard, they must know and agree.")}</li>
          <li>{L("Tu sesión se guarda cifrada para tu usuario de Windows y «Cerrar sesión» la borra. El registro de instalación no contiene datos personales ni contraseñas.", "Your session is stored encrypted for your Windows user and «Sign out» deletes it. The installation log contains no personal data or passwords.")}</li>
        </ul>
      </section>

      <section className="panel">
        <h2>{L("Manual de instalación", "Installation guide")}</h2>
        <ol>
          <li>{L("Descarga el instalador con el botón de arriba y comprueba su SHA-256 (sección siguiente).", "Download the installer with the button above and check its SHA-256 (next section).")}</li>
          <li>{L("Ábrelo. El asistente se maneja con teclado: Tab para moverse, Espacio para marcar casillas, Intro para continuar y Escape para cancelar. Los lectores de pantalla leen cada paso.", "Open it. The wizard works with the keyboard: Tab to move, Space to tick boxes, Enter to continue and Escape to cancel. Screen readers read each step.")}</li>
          <li>{L("Lee qué se instala y dónde, elige si quieres un acceso directo en el escritorio y pulsa «Instalar». No pide permisos de administrador.", "Read what is installed and where, choose whether you want a desktop shortcut and press «Install». It doesn't ask for administrator rights.")}</li>
          <li>{L("Al terminar, abre «AINGEL Desktop» desde el menú Inicio y entra con tu cuenta. Para actualizar, instala la versión nueva encima: tus preferencias se conservan.", "When it finishes, open «AINGEL Desktop» from the Start menu and sign in. To update, install the new version over it: your preferences are kept.")}</li>
        </ol>
      </section>

      <section className="panel">
        <h2>{L("Verificar la integridad", "Check its integrity")}</h2>
        <p>{L("En PowerShell, dentro de la carpeta de descargas, escribe:", "In PowerShell, inside the downloads folder, type:")}</p>
        <pre className="code-block"><code>{`Get-FileHash .\\${release?.file ?? "AINGEL-Desktop-Setup-<versión>.exe"} -Algorithm SHA256`}</code></pre>
        <p>{L("El resultado debe ser exactamente la huella SHA-256 publicada arriba. Si no coincide, no lo abras y descárgalo otra vez. Además, el instalador comprueba por dentro que su contenido no se haya alterado antes de copiar nada.", "The result must be exactly the SHA-256 fingerprint published above. If it doesn't match, don't open it and download it again. The installer also checks inside that its content wasn't altered before copying anything.")}</p>
      </section>

      <section className="panel">
        <h2>{L("Desinstalar", "Uninstall")}</h2>
        <p>{L("Configuración › Aplicaciones › Aplicaciones instaladas › AINGEL Desktop › Desinstalar. El desinstalador quita el programa, el menú Inicio y el acceso directo; te pregunta si también quieres borrar tus preferencias y la sesión guardada. Tu cuenta de AINGEL no se toca.", "Settings › Apps › Installed apps › AINGEL Desktop › Uninstall. The uninstaller removes the program, the Start menu entry and the shortcut; it asks whether you also want to delete your preferences and saved session. Your AINGEL account isn't affected.")}</p>
      </section>
    </div>
  );
}
