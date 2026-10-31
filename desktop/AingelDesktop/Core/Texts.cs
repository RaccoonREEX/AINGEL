using System;
using System.Collections.Generic;

namespace Aingel.Desktop.Core;

/// <summary>Interface texts in Ecuadorian Spanish and English (the profile's locale).</summary>
public static class Texts
{
    static readonly Dictionary<string, (string Es, string En)> All = new()
    {
        ["title"] = ("AINGEL", "AINGEL"),
        ["login_title"] = ("Entrar en AINGEL", "Sign in to AINGEL"),
        ["server"] = ("Servidor", "Server"),
        ["username"] = ("Usuario", "Username"),
        ["password"] = ("Contraseña", "Password"),
        ["mfa_code"] = ("Código de verificación", "Verification code"),
        ["sign_in"] = ("Entrar", "Sign in"),
        ["verify"] = ("Verificar", "Verify"),
        ["profile"] = ("Perfil", "Profile"),
        ["continue"] = ("Continuar", "Continue"),
        ["signing_in"] = ("Entrando…", "Signing in…"),
        ["mfa_needed"] = ("Escribe el código de tu aplicación de verificación.", "Enter the code from your authenticator app."),
        ["pick_profile"] = ("Elige el perfil con el que vas a usar AINGEL.", "Choose the profile you will use AINGEL with."),
        ["no_profiles"] = ("Esta cuenta no tiene perfiles. Créalo primero en la web o en el móvil.", "This account has no profiles. Create one first on the web or the phone."),
        ["idle"] = ("Listo. Pulsa Ctrl+Alt+D para describir la ventana activa.", "Ready. Press Ctrl+Alt+D to describe the active window."),
        ["capturing"] = ("Capturando: {0}", "Capturing: {0}"),
        ["thinking"] = ("AINGEL está mirando la imagen…", "AINGEL is looking at the image…"),
        ["thinking_deep"] = ("AINGEL está analizando a fondo; puede tardar hasta un minuto…", "AINGEL is analysing in depth; it can take up to a minute…"),
        ["captured_ask"] = ("Capturé «{0}». Escribe tu pregunta y pulsa Intro. Escape cancela.", "Captured «{0}». Type your question and press Enter. Escape cancels."),
        ["capture_cancelled"] = ("Captura descartada.", "Capture discarded."),
        ["describe_window"] = ("Describir ventana activa", "Describe active window"),
        ["describe_screen"] = ("Describir pantalla completa", "Describe whole screen"),
        ["read_focus"] = ("Leer elemento con foco", "Read focused element"),
        ["more_detail"] = ("Explorar a fondo", "Explore in depth"),
        ["stop_speech"] = ("Detener voz", "Stop speaking"),
        ["question"] = ("Pregunta sobre la pantalla", "Question about the screen"),
        ["ask"] = ("Preguntar", "Ask"),
        ["answer"] = ("Respuesta de AINGEL", "AINGEL's answer"),
        ["level"] = ("Nivel de detalle", "Level of detail"),
        ["level_auto"] = ("Según la pregunta", "From the question"),
        ["level_brief"] = ("Breve", "Brief"),
        ["level_standard"] = ("Estándar", "Standard"),
        ["level_detailed"] = ("Detallada", "Detailed"),
        ["level_deep"] = ("A fondo", "In depth"),
        ["voice"] = ("Voz de AINGEL", "AINGEL's voice"),
        ["voice_reader"] = ("Hay un lector de pantalla activo: AINGEL no habla para no superponerse; el lector anuncia la respuesta.", "A screen reader is running: AINGEL stays quiet so voices do not overlap; the reader announces the answer."),
        ["topmost"] = ("Siempre visible", "Always on top"),
        ["private_test"] = ("Prueba privada de mi propia pantalla", "Private test of my own screen"),
        ["private_confirm"] = ("Vas a enviar a Meta capturas de tu propia pantalla para una prueba privada. Usa solo material propio, sin datos de salud ni de otras personas: AINGEL no detecta ese contenido automáticamente. El servidor comprueba tus permisos en cada captura. ¿Activar la prueba privada hasta cerrar AINGEL?", "You are about to send captures of your own screen to Meta for a private test. Use only your own material, without health information or other people: AINGEL does not detect that content automatically. The server checks your permissions on every capture. Turn on the private test until AINGEL closes?"),
        ["synthetic"] = ("Modo de prueba sintética (no captura tu pantalla)", "Synthetic test mode (does not capture your screen)"),
        ["synthetic_note"] = ("Prueba sintética: AINGEL describe una pantalla ficticia dibujada por el servidor; no se captura nada.", "Synthetic test: AINGEL describes a fictitious screen drawn by the server; nothing is captured."),
        ["sign_out"] = ("Cerrar sesión", "Sign out"),
        ["privacy_note"] = ("AINGEL solo captura cuando lo pides, nunca en segundo plano, y su propia ventana no aparece en las capturas. La imagen se envía a Meta; para tus preguntas de seguimiento el servidor la guarda cifrada hasta 15 minutos y luego la borra. El contenido protegido (por ejemplo, vídeo con DRM) aparece en negro y AINGEL no lo evita.", "AINGEL only captures when you ask, never in the background, and its own window is left out of captures. The image is sent to Meta; for your follow-up questions the server keeps it encrypted for up to 15 minutes, then deletes it. Protected content (such as DRM video) comes out black and AINGEL does not get around that."),
        ["shortcuts"] = ("Atajos: Ctrl+Alt+D ventana activa · Ctrl+Alt+P pantalla completa · Ctrl+Alt+Q preguntar · Ctrl+Alt+M a fondo · Ctrl+Alt+F elemento con foco · Ctrl+Alt+S detener voz · Ctrl+Alt+A mostrar u ocultar AINGEL", "Shortcuts: Ctrl+Alt+D active window · Ctrl+Alt+P whole screen · Ctrl+Alt+Q ask · Ctrl+Alt+M in depth · Ctrl+Alt+F focused element · Ctrl+Alt+S stop speaking · Ctrl+Alt+A show or hide AINGEL"),
        ["hotkeys_failed"] = ("Otro programa ya usa estos atajos; usa los botones: {0}", "Another program already uses these shortcuts; use the buttons: {0}"),
        ["no_window"] = ("No encuentro una ventana visible para describir. Abre o selecciona la ventana y vuelve a intentarlo.", "I can't find a visible window to describe. Open or select the window and try again."),
        ["no_session"] = ("Primero describe una ventana o la pantalla; luego puedes pedir más detalle.", "Describe a window or the screen first; then you can ask for more detail."),
        ["focus_none"] = ("No hay ningún elemento con el foco del teclado.", "No element has the keyboard focus."),
        ["mock_note"] = ("Modo de prueba del servidor: la imagen no se analizó.", "Server test mode: the image was not analysed."),
        ["e_network_failed"] = ("No hay conexión con el servidor de AINGEL.", "There is no connection to the AINGEL server."),
        ["e_timeout"] = ("El servidor tardó demasiado. Inténtalo de nuevo.", "The server took too long. Please try again."),
        ["e_credentials_invalid"] = ("Usuario o contraseña incorrectos.", "Wrong username or password."),
        ["e_mfa_code_invalid"] = ("El código no es válido.", "The code is not valid."),
        ["e_mfa_challenge_expired"] = ("El código caducó. Vuelve a entrar.", "The code expired. Sign in again."),
        ["e_auth_rate_limited"] = ("Demasiados intentos. Espera unos minutos.", "Too many attempts. Wait a few minutes."),
        ["e_authentication_required"] = ("La sesión terminó. Vuelve a entrar.", "The session ended. Sign in again."),
        ["e_privacy_review_required"] = ("Para describir tu pantalla, el servidor necesita tus permisos de imágenes («Usar la cámara» y «Enviar fotos a Meta», en Personalizar desde la web o el móvil), o la prueba privada activada aquí.", "To describe your screen the server needs your image permissions («Use the camera» and «Send photos to Meta», in Personalize on the web or phone), or the private test turned on here."),
        ["e_camera_consent_revoked"] = ("Retiraste el permiso de imágenes. AINGEL no enviará capturas hasta que lo vuelvas a dar.", "You withdrew the image permission. AINGEL will not send captures until you grant it again."),
        ["e_consent_changed"] = ("Tus permisos cambiaron mientras AINGEL miraba: descarté la respuesta y la imagen.", "Your permissions changed while AINGEL was looking: I discarded the answer and the image."),
        ["e_meta_access_denied"] = ("Esta cuenta no tiene acceso a Meta en este servidor.", "This account has no Meta access on this server."),
        ["e_adult_declaration_required"] = ("Esta cuenta debe confirmar que es mayor de edad en la web o el móvil.", "This account must confirm it is an adult on the web or phone."),
        ["e_visual_session_expired"] = ("Ya no tengo esa imagen. Describe la ventana otra vez para seguir preguntando.", "I no longer have that image. Describe the window again to keep asking."),
        ["e_synthetic_tests_disabled"] = ("Este servidor no tiene activadas las pruebas sintéticas.", "This server does not have synthetic tests turned on."),
        ["e_private_test_consent_required"] = ("La prueba privada solo está disponible en tu propio perfil.", "The private test is only available on your own profile."),
        ["e_throttled"] = ("Demasiadas peticiones seguidas. Espera un momento.", "Too many requests in a row. Wait a moment."),
        ["e_meta_budget_exhausted"] = ("Se alcanzó el presupuesto de uso de Meta configurado en el servidor.", "The Meta usage budget set on the server has been reached."),
        ["e_window_not_visible"] = ("Esa ventana está minimizada u oculta.", "That window is minimized or hidden."),
        ["e_backend_invalid"] = ("La dirección del servidor no es válida. Usa https://, o http:// solo para un servidor de prueba en este equipo.", "The server address is not valid. Use https://, or http:// only for a test server on this computer."),
        ["e_capture_failed"] = ("No pude capturar la pantalla. Inténtalo de nuevo.", "I couldn't capture the screen. Please try again."),
        ["e_other"] = ("No pude analizar la pantalla ahora. Inténtalo de nuevo.", "I couldn't analyse the screen right now. Please try again."),
    };

    public static string Get(string locale, string key, params object[] args)
    {
        var (es, en) = All.TryGetValue(key, out var value) ? value : All["e_other"];
        var text = locale.StartsWith("es", StringComparison.OrdinalIgnoreCase) ? es : en;
        return args.Length > 0 ? string.Format(text, args) : text;
    }

    /// <summary>The message for an error code; unknown codes (including Meta failures) get a generic one.</summary>
    public static string Error(string locale, string code) => Get(locale, All.ContainsKey("e_" + code) ? "e_" + code : "e_other");

    internal static bool Has(string key) => All.ContainsKey(key);
}
