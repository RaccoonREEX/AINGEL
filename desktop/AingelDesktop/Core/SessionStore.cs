using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Aingel.Desktop.Core;

/// <summary>Plain settings (no secrets): which server, which profile, voice and window choices.</summary>
public sealed class Settings
{
    public string Backend { get; set; } = Core.Backend.Default;
    public string? ProfileId { get; set; }
    public bool? Voice { get; set; }
    public bool Topmost { get; set; } = true;
}

/// <summary>
/// The session cookies, encrypted with Windows DPAPI for this Windows user only, and the plain settings, under
/// %LOCALAPPDATA%\AINGEL\Desktop. Signing out deletes the cookies.
/// </summary>
public sealed class SessionStore
{
    static readonly byte[] Entropy = Encoding.UTF8.GetBytes("AINGEL Desktop session v1");
    readonly string folder;

    public SessionStore(string? folder = null)
    {
        this.folder = folder ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AINGEL", "Desktop");
        Directory.CreateDirectory(this.folder);
    }

    string SessionPath => Path.Combine(folder, "session.bin");
    string SettingsPath => Path.Combine(folder, "settings.json");

    public Settings LoadSettings()
    {
        try { return JsonSerializer.Deserialize<Settings>(File.ReadAllText(SettingsPath)) ?? new Settings(); }
        catch (Exception e) when (e is IOException or JsonException or UnauthorizedAccessException) { return new Settings(); }
    }

    public void SaveSettings(Settings settings) => File.WriteAllText(SettingsPath, JsonSerializer.Serialize(settings));

    sealed record StoredCookie(string Name, string Value, string Domain, string Path, bool Secure, bool HttpOnly, DateTime Expires);

    /// <summary>Saves the cookies of [baseUrl] only.</summary>
    public void SaveCookies(CookieContainer cookies, Uri baseUrl)
    {
        var rows = cookies.GetCookies(baseUrl).Cast<Cookie>()
            .Select(c => new StoredCookie(c.Name, c.Value, c.Domain, c.Path, c.Secure, c.HttpOnly, c.Expires)).ToList();
        var sealedBytes = ProtectedData.Protect(JsonSerializer.SerializeToUtf8Bytes(rows), Entropy, DataProtectionScope.CurrentUser);
        File.WriteAllBytes(SessionPath, sealedBytes);
    }

    /// <summary>The saved cookies for [baseUrl], or an empty container (none, another user's file, or damaged).</summary>
    public CookieContainer LoadCookies(Uri baseUrl)
    {
        var container = new CookieContainer();
        try
        {
            var rows = JsonSerializer.Deserialize<List<StoredCookie>>(ProtectedData.Unprotect(File.ReadAllBytes(SessionPath), Entropy, DataProtectionScope.CurrentUser));
            foreach (var row in rows ?? new List<StoredCookie>())
            {
                if (row.Expires != DateTime.MinValue && row.Expires < DateTime.Now) continue;
                container.Add(baseUrl, new Cookie(row.Name, row.Value, row.Path, row.Domain) { Secure = row.Secure, HttpOnly = row.HttpOnly, Expires = row.Expires });
            }
        }
        catch (Exception e) when (e is IOException or CryptographicException or JsonException or CookieException or UnauthorizedAccessException) { }
        return container;
    }

    public void ClearCookies()
    {
        try { File.Delete(SessionPath); } catch (IOException) { }
    }
}
