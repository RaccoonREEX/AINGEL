using System;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Aingel.Desktop.Core;

/// <summary>One transcription event: a partial or final line of a turn, or the speaker label Meta reports.</summary>
public sealed record CaptionEvent(string Kind, string? TurnId, string Text, bool Final, string? Speaker);

/// <summary>
/// Live captions over the server's WebSocket (backend assistance.captions → Meta Voice Transcribe): the session
/// cookie and the server's own origin, a start message with the person's authorization, then 24 kHz mono 16-bit
/// audio frames. The server rechecks consent while streaming and ends a session after 10 minutes.
/// </summary>
public sealed class CaptionsClient : IAsyncDisposable
{
    readonly ClientWebSocket socket = new();
    readonly SemaphoreSlim sending = new(1, 1);
    readonly CancellationTokenSource closing = new();
    Task? receiver;

    public event Action<CaptionEvent>? Caption;
    /// <summary>The session ended: null when closed normally, else the server's error code.</summary>
    public event Action<string?>? Ended;

    /// <summary>The start message: «source: system» (the computer's audio, which may hold other people's voices and has
    /// its own purpose, care.consent.meta_meeting_audio), the person's profile and, only when they chose it, the
    /// private test declaration.
    /// Never «synthetic» or «fixture»: the server refuses captions that are not the person's own authorized audio.</summary>
    internal static string StartMessage(Profile profile, bool privateTest)
    {
        if (privateTest && !VisionFields.PrivateTestAllowed(profile)) throw new ApiFailure("private_test_consent_required");
        return privateTest
            ? JsonSerializer.Serialize(new { type = "start", locale = profile.Locale, profile = profile.Id, source = "system", private_test = true })
            : JsonSerializer.Serialize(new { type = "start", locale = profile.Locale, profile = profile.Id, source = "system" });
    }

    internal static Uri Endpoint(Uri api) => new($"{(api.Scheme == Uri.UriSchemeHttps ? "wss" : "ws")}://{api.Authority}/ws/captions/");

    /// <summary>Connects and waits for «ready» (or throws ApiFailure with the server's code).</summary>
    public async Task Start(ApiClient api, Profile profile, bool privateTest, CancellationToken token = default)
    {
        socket.Options.Cookies = api.Cookies;
        socket.Options.SetRequestHeader("Origin", api.Base.GetLeftPart(UriPartial.Authority));
        try { await socket.ConnectAsync(Endpoint(api.Base), token); }
        catch (WebSocketException) { throw new ApiFailure(ApiClient.NetworkFailed); }
        await SendText(StartMessage(profile, privateTest), token);
        var first = await ReadMessage(token) ?? throw new ApiFailure("transcription_unavailable");
        using var ready = JsonDocument.Parse(first);
        var type = ready.RootElement.GetProperty("type").GetString();
        if (type == "error") throw new ApiFailure(ready.RootElement.GetProperty("code").GetString() ?? "transcription_unavailable");
        if (type != "ready" || ready.RootElement.GetProperty("sample_rate").GetInt32() != PcmConverter.TargetRate)
            throw new ApiFailure("transcription_unavailable");
        receiver = Task.Run(Receive);
    }

    async Task<string?> ReadMessage(CancellationToken token)
    {
        var buffer = new byte[16384];
        var text = new StringBuilder();
        while (true)
        {
            WebSocketReceiveResult result;
            try { result = await socket.ReceiveAsync(buffer, token); }
            catch (WebSocketException) { return null; }
            if (result.MessageType == WebSocketMessageType.Close) return null;
            text.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
            if (text.Length > 64_000) return null;
            if (result.EndOfMessage) return text.ToString();
        }
    }

    async Task Receive()
    {
        string? reason = null;
        try
        {
            while (await ReadMessage(closing.Token) is { } message)
            {
                using var document = JsonDocument.Parse(message);
                var root = document.RootElement;
                var type = root.GetProperty("type").GetString();
                if (type == "error") { reason = root.TryGetProperty("code", out var code) ? code.GetString() : "transcription_unavailable"; break; }
                if (type == "closed") break;
                if (Parse(root) is { } caption) Caption?.Invoke(caption);
            }
        }
        catch (Exception e) when (e is OperationCanceledException or JsonException or InvalidOperationException) { }
        Ended?.Invoke(reason);
    }

    /// <summary>A transcription event, or null for events with nothing to show.</summary>
    internal static CaptionEvent? Parse(JsonElement root)
    {
        string? Text(string name) => root.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() : null;
        var type = Text("type") ?? "";
        var turn = root.TryGetProperty("turnId", out var id) ? id.ToString() : null;
        return type switch
        {
            "transcript" => new CaptionEvent(type, turn, Text("transcript") ?? "", root.TryGetProperty("final", out var final) && final.ValueKind == JsonValueKind.True, null),
            "speaker" when Text("label") is { Length: > 0 } label => new CaptionEvent(type, turn, "", false, label),
            "speechComplete" => new CaptionEvent(type, turn, "", true, null),
            _ => null,
        };
    }

    async Task SendText(string text, CancellationToken token)
    {
        await sending.WaitAsync(token);
        try { await socket.SendAsync(Encoding.UTF8.GetBytes(text), WebSocketMessageType.Text, true, token); }
        finally { sending.Release(); }
    }

    /// <summary>One 200 ms audio frame; returns false once the connection is gone.</summary>
    public async Task<bool> SendAudio(byte[] frame)
    {
        if (socket.State != WebSocketState.Open) return false;
        await sending.WaitAsync();
        try { await socket.SendAsync(frame, WebSocketMessageType.Binary, true, CancellationToken.None); return true; }
        catch (Exception e) when (e is WebSocketException or ObjectDisposedException) { return false; }
        finally { sending.Release(); }
    }

    /// <summary>Asks the server to finish the last sentence; the final events still arrive, then «closed».</summary>
    public async Task Stop()
    {
        if (socket.State == WebSocketState.Open)
        {
            try { await SendText("{\"type\":\"stop\"}", CancellationToken.None); } catch (WebSocketException) { }
        }
    }

    public async ValueTask DisposeAsync()
    {
        closing.Cancel();
        try
        {
            if (socket.State == WebSocketState.Open)
                await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "", CancellationToken.None);
        }
        catch (Exception e) when (e is WebSocketException or OperationCanceledException) { }
        if (receiver != null) { try { await receiver; } catch (ObjectDisposedException) { } }
        socket.Dispose();
    }
}
