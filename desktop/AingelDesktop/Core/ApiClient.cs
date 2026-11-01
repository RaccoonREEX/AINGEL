using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Aingel.Desktop.Core;

/// <summary>A refused or failed request, with the server's bounded error code (never its raw text).</summary>
public sealed class ApiFailure : Exception
{
    public string Code { get; }
    public int Status { get; }
    public ApiFailure(string code, int status = 0) : base(code) { Code = code; Status = status; }
}

public sealed record Profile(string Id, string DisplayName, string Locale, string Role, string SubjectStatus);

/// <summary>
/// The AINGEL HTTP API (backend care and assistance apps) with the same rules as the Android client: the session
/// cookie, and on every write the CSRF token plus a same-origin Origin header. A write refused for CSRF is retried
/// once after refreshing the token.
/// </summary>
public sealed class ApiClient : IDisposable
{
    public const string NetworkFailed = "network_failed";
    public const string CsrfFailed = "csrf_failed";
    readonly HttpClient http;
    string csrf = "";

    public Uri Base { get; }
    public CookieContainer Cookies { get; }

    public ApiClient(string baseUrl, CookieContainer? cookies = null)
    {
        Base = new Uri(Backend.Validate(baseUrl) ?? throw new ApiFailure("backend_invalid"));
        Cookies = cookies ?? new CookieContainer();
        // No redirects: a redirect could carry the session elsewhere. Deep vision can take about a minute.
        var handler = new HttpClientHandler { CookieContainer = Cookies, UseCookies = true, AllowAutoRedirect = false };
        http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(200) };
        http.DefaultRequestHeaders.UserAgent.ParseAdd("AINGEL-Desktop/0.1");
    }

    string Origin => Base.GetLeftPart(UriPartial.Authority);

    async Task<JsonElement> Send(HttpMethod method, string path, Func<HttpContent?> content, CancellationToken token)
    {
        var write = method != HttpMethod.Get;
        if (write && csrf.Length == 0) await RefreshCsrf(token);
        for (var attempt = 0; ; attempt++)
        {
            using var request = new HttpRequestMessage(method, new Uri(Base, "api/v1/" + path)) { Content = content() };
            request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
            if (write)
            {
                request.Headers.Add("X-CSRFToken", csrf);
                request.Headers.Add("Origin", Origin);
                request.Headers.Referrer = Base;
            }
            HttpResponseMessage response;
            try { response = await http.SendAsync(request, token); }
            catch (HttpRequestException) { throw new ApiFailure(NetworkFailed); }
            catch (TaskCanceledException) when (!token.IsCancellationRequested) { throw new ApiFailure("timeout"); }
            using (response)
            {
                var status = (int)response.StatusCode;
                if (status == 204) return default;
                var body = await response.Content.ReadAsStringAsync(token);
                JsonElement json = default;
                var parsed = false;
                try { json = JsonDocument.Parse(body).RootElement.Clone(); parsed = true; } catch (JsonException) { }
                if (response.IsSuccessStatusCode)
                {
                    if (!parsed) throw new ApiFailure("response_invalid", status);
                    if (json.ValueKind == JsonValueKind.Object && json.TryGetProperty("csrf", out var fresh) && fresh.ValueKind == JsonValueKind.String) csrf = fresh.GetString()!;
                    return json;
                }
                var code = ErrorCode(status, parsed ? json : null, body);
                if (code == CsrfFailed && write && attempt == 0) { await RefreshCsrf(token); continue; }
                throw new ApiFailure(code, status);
            }
        }
    }

    /// <summary>The server's error code: {"error": code} from AINGEL views, DRF's CSRF detail, or Django's CSRF page.</summary>
    internal static string ErrorCode(int status, JsonElement? json, string body)
    {
        if (json is { ValueKind: JsonValueKind.Object } value)
        {
            if (value.TryGetProperty("error", out var error) && error.ValueKind == JsonValueKind.String) return error.GetString()!;
            if (value.TryGetProperty("detail", out var detail) && detail.ValueKind == JsonValueKind.String && detail.GetString()!.StartsWith("CSRF Failed")) return CsrfFailed;
        }
        if (status == 403 && json is null && body.Contains("CSRF")) return CsrfFailed;
        return status switch { 401 => "authentication_required", 403 => "permission_denied", 404 => "not_found", 429 => "throttled", >= 500 => "server_error", _ => "request_invalid" };
    }

    async Task RefreshCsrf(CancellationToken token) => await Send(HttpMethod.Get, "auth/session/", () => null, token);

    static StringContent Json(object value) => new(JsonSerializer.Serialize(value), Encoding.UTF8, "application/json");

    public Task<JsonElement> SessionState(CancellationToken token = default) => Send(HttpMethod.Get, "auth/session/", () => null, token);

    /// <summary>Signs in; the answer says whether a second factor is needed ("mfa_required").</summary>
    public Task<JsonElement> Login(string username, string password, CancellationToken token = default) =>
        Send(HttpMethod.Post, "auth/login/", () => Json(new { username, password }), token);

    public Task<JsonElement> VerifyMfa(string code, CancellationToken token = default) =>
        Send(HttpMethod.Post, "auth/mfa/verify/", () => Json(new { code }), token);

    public Task<JsonElement> Logout(CancellationToken token = default) => Send(HttpMethod.Post, "auth/logout/", () => Json(new { }), token);

    public async Task<IReadOnlyList<Profile>> Profiles(CancellationToken token = default)
    {
        var rows = await Send(HttpMethod.Get, "profiles/", () => null, token);
        if (rows.ValueKind != JsonValueKind.Array) throw new ApiFailure("response_invalid");
        static string Text(JsonElement row, string name, string fallback = "") =>
            row.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String ? value.GetString()! : fallback;
        return rows.EnumerateArray()
            .Select(row => new Profile(Text(row, "id"), Text(row, "display_name"), Text(row, "locale", "es-EC"), Text(row, "role"), Text(row, "subject_status")))
            .Where(profile => profile.Id.Length > 0)
            .ToList();
    }

    /// <summary>Deep vision (`vision/`): [jpeg] with [fields], or a follow-up or server fixture when [jpeg] is null.</summary>
    public Task<JsonElement> Vision(byte[]? jpeg, IReadOnlyDictionary<string, string> fields, CancellationToken token = default) =>
        Send(HttpMethod.Post, "vision/", () => Multipart(jpeg, fields), token);

    /// <summary>Ends a follow-up session now: the server deletes its copy of the picture.</summary>
    public async Task CloseVision(string session, CancellationToken token = default)
    {
        if (session.Any(c => !(char.IsAsciiLetterOrDigit(c) || c is '-' or '_'))) return;
        try { await Send(HttpMethod.Delete, $"vision/sessions/{session}/", () => null, token); } catch (ApiFailure) { }
    }

    // --- Updates ---------------------------------------------------------------------------------------------------

    /// <summary>The version published on the same server's download page (downloads/manifest.json, written by
    /// Build-Installer.ps1), or null. AINGEL only tells the person: it never downloads or runs an update itself.</summary>
    public async Task<string?> LatestRelease(CancellationToken token = default)
    {
        try
        {
            using var response = await http.GetAsync(new Uri(Base, "downloads/manifest.json"), token);
            if (!response.IsSuccessStatusCode) return null;
            using var manifest = JsonDocument.Parse(await response.Content.ReadAsStringAsync(token));
            return manifest.RootElement.TryGetProperty("version", out var version) && version.ValueKind == JsonValueKind.String ? version.GetString() : null;
        }
        catch (Exception e) when (e is HttpRequestException or JsonException or TaskCanceledException) { return null; }
    }

    /// <summary>True when [published] is a higher dotted version than [current].</summary>
    public static bool Newer(string? published, string current) =>
        System.Version.TryParse(published, out var latest) && System.Version.TryParse(current, out var installed) && latest > installed;

    // --- Documents (backend assistance.documents) ----------------------------------------------------------------

    /// <summary>Opens a PDF or a page photo ([file] named [name]), or a server fixture when [file] is null.</summary>
    public Task<JsonElement> OpenDocument(byte[]? file, string name, IReadOnlyDictionary<string, string> fields, CancellationToken token = default)
    {
        var type = name.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase) ? "application/pdf" : "image/jpeg";
        return Send(HttpMethod.Post, "documents/", () => Multipart(file, fields, "file", name, type), token);
    }

    public Task<JsonElement> DocumentPage(string document, int page, CancellationToken token = default) =>
        Send(HttpMethod.Get, $"documents/{Segment(document)}/pages/{page}/", () => null, token);

    public Task<JsonElement> TranscribePage(string document, int page, CancellationToken token = default) =>
        Send(HttpMethod.Post, $"documents/{Segment(document)}/pages/{page}/transcribe/", () => Json(new { }), token);

    public Task<JsonElement> SearchDocument(string document, string query, CancellationToken token = default) =>
        Send(HttpMethod.Get, $"documents/{Segment(document)}/search/?q={Uri.EscapeDataString(query)}", () => null, token);

    /// <summary>Explain, summarize, figures or a question; only a question carries typed text.</summary>
    public Task<JsonElement> AskDocument(string document, string action, int page, string scope, string? question, CancellationToken token = default)
    {
        var body = new Dictionary<string, object> { ["action"] = action, ["page"] = page, ["scope"] = scope };
        if (action == "question" && !string.IsNullOrWhiteSpace(question)) body["question"] = question.Length > 600 ? question[..600] : question;
        return Send(HttpMethod.Post, $"documents/{Segment(document)}/ask/", () => Json(body), token);
    }

    public async Task CloseDocument(string document, CancellationToken token = default)
    {
        try { await Send(HttpMethod.Delete, $"documents/{Segment(document)}/", () => null, token); } catch (ApiFailure) { }
    }

    /// <summary>A server token as one URL segment, never an arbitrary path.</summary>
    internal static string Segment(string value) =>
        value.Length is >= 16 and <= 64 && value.All(c => char.IsAsciiLetterOrDigit(c) || c is '-' or '_') ? value : throw new ApiFailure("document_expired");

    internal static MultipartFormDataContent Multipart(byte[]? jpeg, IReadOnlyDictionary<string, string> fields) =>
        Multipart(jpeg, fields, "image", "screen.jpg", "image/jpeg");

    internal static MultipartFormDataContent Multipart(byte[]? file, IReadOnlyDictionary<string, string> fields, string partName, string fileName, string type)
    {
        var form = new MultipartFormDataContent();
        // Fields first, so the server can refuse before reading the file.
        foreach (var (name, value) in fields)
        {
            var part = new StringContent(value, Encoding.UTF8);
            part.Headers.ContentType = null;
            part.Headers.ContentDisposition = new ContentDispositionHeaderValue("form-data") { Name = $"\"{name}\"" };
            form.Add(part);
        }
        if (file != null)
        {
            var content = new ByteArrayContent(file);
            content.Headers.ContentType = new MediaTypeHeaderValue(type);
            // Quotes, backslashes and control characters would break the header: they are left out of the name.
            var safe = new string(fileName.Where(c => c >= ' ' && c != '"' && c != '\\').ToArray());
            content.Headers.ContentDisposition = new ContentDispositionHeaderValue("form-data") { Name = $"\"{partName}\"", FileName = $"\"{safe}\"" };
            form.Add(content);
        }
        return form;
    }

    public void Dispose() => http.Dispose();
}
