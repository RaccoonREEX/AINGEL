using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using Aingel.Desktop.Core;

namespace Aingel.Desktop.Tests;

/// <summary>
/// Checks for AINGEL Desktop's core. Without AINGEL_TEST_BACKEND only local checks run; with it (a local server in
/// test mode, plus AINGEL_TEST_USER and AINGEL_TEST_PASSWORD for a local test account) the API is exercised too.
/// </summary>
static class Program
{
    static int failures, passed;

    static void Check(bool condition, string name)
    {
        if (condition) passed++;
        else { failures++; Console.WriteLine("FAIL " + name); }
    }

    static async Task<int> Main(string[] args)
    {
        if (args.Length == 2 && args[0] == "--screenshots") { Screenshots.Run(args[1]); return 0; }
        BackendUrls();
        Fields();
        Focus();
        Errors();
        Texts();
        Voices();
        Jpeg();
        Capture();
        PrivacyChecks.Run(Check);
        AudioChecks.Run(Check);
        InstallerChecks.Run(Check);
        Cookies();
        await Multipart();
        var backend = Environment.GetEnvironmentVariable("AINGEL_TEST_BACKEND");
        if (!string.IsNullOrEmpty(backend)) await LocalServer(backend);
        else Console.WriteLine("skip local server checks (AINGEL_TEST_BACKEND not set)");
        Console.WriteLine($"{passed} passed, {failures} failed");
        return failures == 0 ? 0 : 1;
    }

    static void BackendUrls()
    {
        Check(Backend.Validate("https://aingel.mapatechstudio.com") == "https://aingel.mapatechstudio.com/", "https host");
        Check(Backend.Validate("http://127.0.0.1:8010/") == "http://127.0.0.1:8010/", "loopback http");
        Check(Backend.Validate("http://localhost:8010") == "http://localhost:8010/", "localhost http");
        Check(Backend.Validate("http://aingel.mapatechstudio.com/") == null, "no plain http elsewhere");
        Check(Backend.Validate("https://user:pass@example.com/") == null, "no credentials in the URL");
        Check(Backend.Validate("https://example.com/api/") == null, "no path");
        Check(Backend.Validate("https://example.com/?x=1") == null, "no query");
        Check(Backend.Validate("ftp://example.com/") == null, "no other schemes");
        Check(Backend.Validate("") == null && Backend.Validate(null) == null, "empty");
    }

    static readonly Profile Own = new("p1", "Mary", "es-EC", "owner", "self");

    static void Fields()
    {
        var screen = VisionFields.Screen(Own, privateTest: true, "  ¿Qué dice el botón azul?  ", "deep");
        Check(screen.Count == 6 && screen["source_kind"] == "screen" && screen["private_test"] == "true" && screen["profile"] == "p1"
              && screen["question"] == "¿Qué dice el botón azul?" && screen["detail_level"] == "deep", "screen fields");
        Check(!VisionFields.Screen(Own, false, null, null).ContainsKey("private_test"), "no declaration unless chosen");
        Check(!VisionFields.Screen(Own, false, null, "maximum").ContainsKey("detail_level"), "unknown level dropped");
        Check(VisionFields.Screen(Own, false, new string('a', 900), null)["question"].Length == 600, "question bounded");
        var caregiver = Own with { Role = "caregiver" };
        Check(Throws(() => VisionFields.Screen(caregiver, true, null, null)) == "private_test_consent_required", "private test only own profile");
        Check(!VisionFields.PrivateTestAllowed(Own with { SubjectStatus = "pending_confirmation" }), "private test needs a confirmed self profile");
        var fixture = VisionFields.Fixture("es-EC", "brief");
        Check(fixture.Keys.OrderBy(k => k).SequenceEqual(new[] { "detail_level", "fixture", "locale", "source_kind" }) && fixture["fixture"] == "screen_desktop", "fixture carries no text or profile");
        var follow = VisionFields.FollowUp("es-EC", "token", "¿Y abajo?", null);
        Check(follow.Keys.OrderBy(k => k).SequenceEqual(new[] { "locale", "question", "session" }), "follow-up carries no profile or declaration");
        Check(VisionFields.EndsSession("consent_changed") && VisionFields.EndsSession("visual_session_expired") && !VisionFields.EndsSession("meta_unavailable"), "session ends");
    }

    static string? Throws(Action action)
    {
        try { action(); return null; } catch (ApiFailure failure) { return failure.Code; }
    }

    static void Focus()
    {
        Check(FocusReader.Phrase("es-EC", "Guardar", "botón", null, false, "Bloc de notas") == "Botón «Guardar». Ventana: Bloc de notas.", "focus phrase");
        var secret = FocusReader.Phrase("es-EC", "Contraseña", "editar", "hunter2", true, null);
        Check(!secret.Contains("hunter2") && secret.Contains("contraseña"), "password content never read");
        Check(FocusReader.Phrase("en-US", "", "edit", new string('x', 500), false, "")!.Contains("…"), "long values bounded");
        Check(FocusReader.Phrase("en-US", null, null, null, false, null) == "Element without a name.", "empty element");
    }

    static void Errors()
    {
        JsonElement Json(string text) => JsonDocument.Parse(text).RootElement;
        Check(ApiClient.ErrorCode(403, Json("{\"error\":\"privacy_review_required\"}"), "") == "privacy_review_required", "AINGEL error code");
        Check(ApiClient.ErrorCode(403, Json("{\"detail\":\"CSRF Failed: CSRF token missing.\"}"), "") == ApiClient.CsrfFailed, "DRF CSRF detail");
        Check(ApiClient.ErrorCode(403, null, "<h1>Forbidden (403)</h1><p>CSRF verification failed.</p>") == ApiClient.CsrfFailed, "Django CSRF page");
        Check(ApiClient.ErrorCode(429, Json("{\"detail\":\"Request was throttled.\"}"), "") == "throttled", "throttled");
        Check(ApiClient.ErrorCode(502, null, "<html>") == "server_error", "server error");
        Check(ApiClient.Segment("abcdefghijklmnop-_12") == "abcdefghijklmnop-_12", "document token segment");
        Check(Throws(() => ApiClient.Segment("../../auth/logout")) == "document_expired", "no path in a token");
    }

    static void Texts()
    {
        Check(Core.Texts.Error("es-EC", "privacy_review_required").Contains("Enviar capturas de tu pantalla a Meta"), "privacy message names the screen permission");
        Check(Core.Texts.Error("en-US", "meta_unavailable") == Core.Texts.Get("en-US", "e_other"), "unknown codes are generic");
        Check(Core.Texts.Error("es-EC", "meta_territory_restricted").Contains("territorios") && Core.Texts.Error("en-US", "territory_declaration_required").Contains("web or phone"), "territory refusals are explained");
        Check(Core.Texts.Get("es-EC", "capturing", "Bloc de notas") == "Capturando: Bloc de notas", "formatted text");
        foreach (var command in Enum.GetValues<Command>()) Check(Core.Texts.Get("es-EC", "shortcuts").Contains(Hotkeys.Label(command)), "shortcut listed " + command);
    }

    static void Voices()
    {
        Check(Speech.PrimaryLanguage("C0A") == 0x0A && Speech.PrimaryLanguage("80A") == 0x0A, "Spanish voices");
        Check(Speech.PrimaryLanguage("409;9") == 0x09, "English voice");
        Check(Speech.PrimaryLanguage("") == -1 && Speech.PrimaryLanguage(null) == -1, "no language");
        Check(Speech.LanguageOf("es-EC") == 0x0A && Speech.LanguageOf("en-US") == 0x09, "profile language");
    }

    static void Jpeg()
    {
        using var big = new Bitmap(3000, 1500);
        using (var graphics = Graphics.FromImage(big)) graphics.Clear(Color.SteelBlue);
        var jpeg = ScreenCapture.Jpeg(big);
        using var decoded = Image.FromStream(new MemoryStream(jpeg));
        Check(jpeg[0] == 0xFF && jpeg[1] == 0xD8 && decoded.Width == 2048 && decoded.Height == 1024, "capture scaled to the server's limit");
        using var small = new Bitmap(800, 600);
        using var kept = Image.FromStream(new MemoryStream(ScreenCapture.Jpeg(small)));
        Check(kept.Width == 800 && kept.Height == 600, "small captures keep their size");
    }

    /// <summary>A real capture of the primary monitor, kept in memory only: nothing is saved or sent.</summary>
    static void Capture()
    {
        try
        {
            var shot = ScreenCapture.Monitor(IntPtr.Zero);
            Check(shot.Jpeg.Length > 1000 && shot.Jpeg[0] == 0xFF && Math.Max(shot.Width, shot.Height) > 0, "monitor captured");
        }
        catch (Exception e) { Check(false, "monitor captured: " + e.GetType().Name + " " + e.Message); }
    }

    static void Cookies()
    {
        var folder = Path.Combine(Path.GetTempPath(), "aingel-desktop-test-" + Guid.NewGuid().ToString("N"));
        try
        {
            var store = new SessionStore(folder);
            var site = new Uri("https://aingel.example.test/");
            var container = new CookieContainer();
            container.Add(site, new Cookie("sessionid", "secret-session-value", "/", "aingel.example.test") { Secure = true, HttpOnly = true });
            store.SaveCookies(container, site);
            var raw = File.ReadAllBytes(Path.Combine(folder, "session.bin"));
            Check(!System.Text.Encoding.UTF8.GetString(raw).Contains("secret-session-value"), "cookies encrypted at rest");
            Check(store.LoadCookies(site).GetCookies(site)["sessionid"]?.Value == "secret-session-value", "cookies restored for this Windows user");
            File.WriteAllBytes(Path.Combine(folder, "session.bin"), new byte[] { 1, 2, 3 });
            Check(store.LoadCookies(site).Count == 0, "damaged session file ignored");
            store.ClearCookies();
            Check(!File.Exists(Path.Combine(folder, "session.bin")), "sign-out deletes cookies");
            store.SaveSettings(new Settings { ProfileId = "p1", Voice = false });
            var settings = store.LoadSettings();
            Check(settings.ProfileId == "p1" && settings.Voice == false && settings.Backend == Backend.Default, "settings round trip");
        }
        finally { Directory.Delete(folder, true); }
    }

    static async Task Multipart()
    {
        var form = ApiClient.Multipart(new byte[] { 0xFF, 0xD8 }, new Dictionary<string, string> { ["locale"] = "es-EC", ["question"] = "¿Qué ves?" });
        var text = await form.ReadAsStringAsync();
        Check(text.IndexOf("name=\"locale\"", StringComparison.Ordinal) < text.IndexOf("name=\"image\"", StringComparison.Ordinal), "fields before the picture");
        Check(text.Contains("¿Qué ves?") && text.Contains("filename=\"screen.jpg\"") && text.Contains("image/jpeg"), "multipart content");
    }

    /// <summary>Documents on the local server: the synthetic book read locally, search, an explanation and a scanned
    /// page (test answers only), and closing.</summary>
    static async Task Documents(ApiClient api, Profile profile)
    {
        var book = await api.OpenDocument(null, "", DocumentWindow.OpenFields(profile, false, "book_pdf"));
        var token = book.GetProperty("document").GetString()!;
        Check(book.GetProperty("pages").GetInt32() == 4 && book.GetProperty("outline").GetArrayLength() == 3, "book opened with its chapters");
        var page = await api.DocumentPage(token, 2);
        Check(page.GetProperty("text").GetString()!.Contains("plantas del jardín y saludaba"), "page text read and joined");
        var found = await api.SearchDocument(token, "gorriones");
        Check(found.GetProperty("results")[0].GetProperty("page").GetInt32() == 4, "search finds the page");
        var explained = await api.AskDocument(token, "explain", 2, "page", null);
        Check(explained.GetProperty("mode").GetString() == "mock", "explanation in test mode");
        Check(Throws(() => api.AskDocument(token, "question", 2, "page", "texto libre").GetAwaiter().GetResult()) == "synthetic_fixture_only", "no free text with a synthetic document");
        await api.CloseDocument(token);
        Check(Throws(() => api.DocumentPage(token, 1).GetAwaiter().GetResult()) == "document_expired", "closed document is gone");
        var scanned = await api.OpenDocument(null, "", DocumentWindow.OpenFields(profile, false, "scanned_pdf"));
        var scannedToken = scanned.GetProperty("document").GetString()!;
        Check(!(await api.DocumentPage(scannedToken, 1)).GetProperty("has_text").GetBoolean(), "scanned page has no text");
        Check((await api.TranscribePage(scannedToken, 1)).GetProperty("mode").GetString() == "mock", "transcription in test mode");
        await api.CloseDocument(scannedToken);
    }

    const string MeetingScript = "Buenos días a todos. Empezamos la reunión del lunes. Primero revisamos el presupuesto del proyecto. " +
        "Después Carla enviará el informe. La próxima reunión será el jueves a las tres de la tarde.";

    /// <summary>A local AINGEL server in test mode (AINGEL_AI_MODE=mock): sign-in with CSRF, profiles, a capture, a
    /// follow-up, the synthetic screen and closing the session. Nothing reaches Meta.</summary>
    static async Task LocalServer(string backend)
    {
        using var api = new ApiClient(backend);
        var user = Environment.GetEnvironmentVariable("AINGEL_TEST_USER") ?? "";
        var password = Environment.GetEnvironmentVariable("AINGEL_TEST_PASSWORD") ?? "";
        Check(Throws(() => api.Login(user, password + "-wrong").GetAwaiter().GetResult()) == "credentials_invalid", "wrong password refused");
        var session = await api.Login(user, password);
        Check(session.GetProperty("user").GetProperty("username").GetString() == user.ToLowerInvariant(), "signed in with CSRF and Origin");
        var profiles = await api.Profiles();
        Check(profiles.Count > 0, "profiles listed");
        var profile = profiles[0];
        if (Environment.GetEnvironmentVariable("AINGEL_TEST_CAPTIONS") == "1")
        {
            // Test G only: the server runs in Meta mode with the private test for this local profile's own audio, so
            // the synthetic-fixture checks below do not apply.
            var finals = await AudioChecks.SyntheticMeeting(api, profile, privateTest: true, MeetingScript);
            Console.WriteLine("captions: " + string.Join(" | ", finals));
            Check(finals.Count > 0, "synthetic meeting captioned");
            await api.Logout();
            return;
        }
        using var bitmap = new Bitmap(640, 400);
        using (var graphics = Graphics.FromImage(bitmap)) graphics.Clear(Color.White);
        var described = await api.Vision(ScreenCapture.Jpeg(bitmap), VisionFields.Screen(profile, false, "¿Qué ves?", "brief"));
        Check(described.GetProperty("mode").GetString() == "mock" && described.GetProperty("level").GetString() == "brief", "screen described in test mode");
        var token = described.GetProperty("session").GetString()!;
        var follow = await api.Vision(null, VisionFields.FollowUp(profile.Locale, token, "¿Y abajo?", null));
        Check(follow.GetProperty("session").GetString() == token, "follow-up on the same picture");
        var fixture = await api.Vision(null, VisionFields.Fixture(profile.Locale, "detailed"));
        Check(fixture.GetProperty("synthetic_fixture").GetString() == "screen_desktop", "synthetic screen");
        Check(Throws(() => api.Vision(null, new Dictionary<string, string>(VisionFields.Fixture("es-EC", null)) { ["question"] = "texto libre" }).GetAwaiter().GetResult()) == "synthetic_fixture_only", "no free text with a fixture");
        await api.CloseVision(token);
        Check(Throws(() => api.Vision(null, VisionFields.FollowUp(profile.Locale, token, "¿Sigue ahí?", null)).GetAwaiter().GetResult()) == "visual_session_expired", "closed session is gone");
        await Documents(api, profile);
        await api.Logout();
        Check(Throws(() => api.Profiles().GetAwaiter().GetResult()) is "authentication_required" or "permission_denied", "signed out");
    }
}
