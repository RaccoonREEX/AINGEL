using System;

namespace Aingel.Desktop.Core;

/// <summary>Which AINGEL server the app talks to.</summary>
public static class Backend
{
    public const string Default = "https://aingel.mapatechstudio.com/";

    /// <summary>
    /// The normalized base URL ("scheme://host[:port]/"), or null. HTTPS for any host; plain HTTP only on this
    /// computer's loopback (a local test server). No credentials, path, query or fragment.
    /// </summary>
    public static string? Validate(string? raw)
    {
        if (!Uri.TryCreate((raw ?? "").Trim(), UriKind.Absolute, out var uri)) return null;
        if (uri.UserInfo.Length > 0 || uri.Query.Length > 0 || uri.Fragment.Length > 0 || uri.AbsolutePath != "/") return null;
        var allowed = uri.Scheme == Uri.UriSchemeHttps || (uri.Scheme == Uri.UriSchemeHttp && uri.IsLoopback);
        return allowed ? uri.GetLeftPart(UriPartial.Authority) + "/" : null;
    }
}
