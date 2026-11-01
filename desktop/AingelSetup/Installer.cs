using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using Microsoft.Win32;

namespace Aingel.Setup;

/// <summary>Where AINGEL Desktop goes for this Windows user. Tests point everything at a temporary folder.</summary>
public sealed record Places(string InstallDir, string StartMenuDir, string DesktopDir, string DataDir, string UninstallKey)
{
    public const string ProductKey = "AINGELDesktop";

    public static Places ForCurrentUser()
    {
        string Folder(Environment.SpecialFolder folder) => Environment.GetFolderPath(folder);
        return new Places(
            Path.Combine(Folder(Environment.SpecialFolder.LocalApplicationData), "Programs", "AINGEL Desktop"),
            Path.Combine(Folder(Environment.SpecialFolder.Programs)),
            Folder(Environment.SpecialFolder.DesktopDirectory),
            Path.Combine(Folder(Environment.SpecialFolder.LocalApplicationData), "AINGEL"),
            @"Software\Microsoft\Windows\CurrentVersion\Uninstall\" + ProductKey);
    }

    public string AppExe => Path.Combine(InstallDir, "AingelDesktop.exe");
    public string Uninstaller => Path.Combine(InstallDir, "AingelUninstall.exe");
    public string StartMenuShortcut => Path.Combine(StartMenuDir, "AINGEL Desktop.lnk");
    public string DesktopShortcut => Path.Combine(DesktopDir, "AINGEL Desktop.lnk");
    public string Log => Path.Combine(DataDir, "install.log");
    /// <summary>Preferences and the encrypted session of the app (SessionStore): never inside the install folder.</summary>
    public string Preferences => Path.Combine(DataDir, "Desktop");
}

public sealed class SetupFailure : Exception
{
    public string Code { get; }
    public SetupFailure(string code) : base(code) => Code = code;
}

/// <summary>
/// Installs, upgrades and uninstalls AINGEL Desktop for the current Windows user, without administrator rights. The
/// embedded app is checked against its SHA-256 before anything is written; upgrades replace the program files and
/// keep the person's preferences, which live elsewhere. The log records steps and paths, never secrets.
/// </summary>
public sealed class Installer
{
    public const string Publisher = "Mapatech Studio";
    public const string DisplayName = "AINGEL Desktop";
    readonly Places places;
    readonly List<string> log = new();

    public Installer(Places places) => this.places = places;

    public static string Version => Assembly.GetExecutingAssembly().GetName().Version?.ToString(3) ?? "0.0.0";

    void Note(string line) => log.Add($"{DateTime.Now:yyyy-MM-dd HH:mm:ss} {line}");

    void WriteLog()
    {
        Directory.CreateDirectory(places.DataDir);
        File.AppendAllLines(places.Log, log);
        log.Clear();
    }

    // --- Requirements ------------------------------------------------------------------------------------------

    /// <summary>Problems that stop the installation: [] when it can go ahead.</summary>
    public static List<string> Requirements(Version windows, long freeBytes, bool appRunning)
    {
        var problems = new List<string>();
        // Windows 10 version 2004 (build 19041): AINGEL keeps its own window out of screen captures from that build.
        if (windows.Major < 10 || (windows.Major == 10 && windows.Build < 19041)) problems.Add("windows_too_old");
        if (freeBytes < 50L * 1024 * 1024) problems.Add("disk_space");
        if (appRunning) problems.Add("app_running");
        return problems;
    }

    public bool AppRunning() => Process.GetProcessesByName("AingelDesktop").Any(process =>
    {
        try { return string.Equals(process.MainModule?.FileName, places.AppExe, StringComparison.OrdinalIgnoreCase); }
        catch (Exception e) when (e is InvalidOperationException or System.ComponentModel.Win32Exception) { return false; }
    });

    public string? InstalledVersion()
    {
        using var key = Registry.CurrentUser.OpenSubKey(places.UninstallKey);
        return key?.GetValue("DisplayVersion") as string;
    }

    // --- Payload -----------------------------------------------------------------------------------------------

    public static string Sha256(byte[] data) => Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();

    /// <summary>The embedded app, after checking it against its embedded SHA-256 (a damaged installer stops here).</summary>
    public static byte[] Payload()
    {
        var assembly = Assembly.GetExecutingAssembly();
        using var zip = assembly.GetManifestResourceStream("payload.zip") ?? throw new SetupFailure("payload_missing");
        using var hash = assembly.GetManifestResourceStream("payload.sha256") ?? throw new SetupFailure("payload_missing");
        using var buffer = new MemoryStream();
        zip.CopyTo(buffer);
        var data = buffer.ToArray();
        var expected = new StreamReader(hash).ReadToEnd().Trim().ToLowerInvariant();
        if (Sha256(data) != expected) throw new SetupFailure("payload_damaged");
        return data;
    }

    // --- Install -------------------------------------------------------------------------------------------------

    /// <summary>Installs [payload] (a zip of the published app), replacing an earlier version's program files only.</summary>
    public void Install(byte[] payload, string setupExe, bool desktopShortcut, string version)
    {
        Note($"install {DisplayName} {version} into {places.InstallDir}");
        var parent = Path.GetDirectoryName(places.InstallDir)!;
        Directory.CreateDirectory(parent);
        var staging = places.InstallDir + ".new";
        if (Directory.Exists(staging)) Directory.Delete(staging, true);
        using (var archive = new ZipArchive(new MemoryStream(payload), ZipArchiveMode.Read))
        {
            foreach (var entry in archive.Entries)
            {
                var target = Path.GetFullPath(Path.Combine(staging, entry.FullName));
                // A zip entry may not point outside the folder («zip slip»).
                if (!target.StartsWith(Path.GetFullPath(staging) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                    throw new SetupFailure("payload_damaged");
                if (entry.FullName.EndsWith('/')) { Directory.CreateDirectory(target); continue; }
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                entry.ExtractToFile(target, overwrite: true);
            }
        }
        if (!File.Exists(Path.Combine(staging, "AingelDesktop.exe"))) throw new SetupFailure("payload_damaged");
        File.Copy(setupExe, Path.Combine(staging, "AingelUninstall.exe"), overwrite: true);
        var upgrade = Directory.Exists(places.InstallDir);
        if (upgrade) Directory.Delete(places.InstallDir, true);  // program files only: preferences live in DataDir
        Directory.Move(staging, places.InstallDir);
        Note(upgrade ? "replaced the earlier program files; preferences kept" : "program files written");
        Directory.CreateDirectory(places.StartMenuDir);
        Shortcut(places.StartMenuShortcut, places.AppExe);
        Note("start menu entry " + places.StartMenuShortcut);
        if (desktopShortcut)
        {
            // Optional: a desktop folder that is missing or redirected must not stop the installation.
            try
            {
                Directory.CreateDirectory(places.DesktopDir);
                Shortcut(places.DesktopShortcut, places.AppExe);
                Note("desktop shortcut " + places.DesktopShortcut);
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or SetupFailure) { Note("desktop shortcut not created"); }
        }
        else if (File.Exists(places.DesktopShortcut)) File.Delete(places.DesktopShortcut);
        Register(version);
        Note("registered in Settings > Apps for this user");
        WriteLog();
    }

    static void Shortcut(string path, string target)
    {
        var type = Type.GetTypeFromProgID("WScript.Shell") ?? throw new SetupFailure("shortcut_failed");
        dynamic shell = Activator.CreateInstance(type)!;
        dynamic link = shell.CreateShortcut(path);
        link.TargetPath = target;
        link.WorkingDirectory = Path.GetDirectoryName(target);
        link.Description = "AINGEL Desktop: asistente de accesibilidad";
        link.IconLocation = target + ",0";
        link.Save();
    }

    void Register(string version)
    {
        using var key = Registry.CurrentUser.CreateSubKey(places.UninstallKey);
        var size = Directory.EnumerateFiles(places.InstallDir, "*", SearchOption.AllDirectories).Sum(file => new FileInfo(file).Length) / 1024;
        key.SetValue("DisplayName", DisplayName);
        key.SetValue("DisplayVersion", version);
        key.SetValue("Publisher", Publisher);
        key.SetValue("InstallLocation", places.InstallDir);
        key.SetValue("DisplayIcon", places.AppExe);
        key.SetValue("UninstallString", $"\"{places.Uninstaller}\" /uninstall");
        key.SetValue("URLInfoAbout", "https://aingel.mapatechstudio.com/");
        key.SetValue("EstimatedSize", (int)size, RegistryValueKind.DWord);
        key.SetValue("NoModify", 1, RegistryValueKind.DWord);
        key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
    }

    // --- Uninstall -----------------------------------------------------------------------------------------------

    /// <summary>Removes the program, its shortcuts and its Settings entry; the preferences and the saved session only
    /// when [removePreferences].</summary>
    public void Uninstall(bool removePreferences)
    {
        Note($"uninstall {DisplayName} from {places.InstallDir}");
        foreach (var link in new[] { places.StartMenuShortcut, places.DesktopShortcut })
            if (File.Exists(link)) File.Delete(link);
        if (Directory.Exists(places.InstallDir)) Directory.Delete(places.InstallDir, true);
        Registry.CurrentUser.DeleteSubKeyTree(places.UninstallKey, throwOnMissingSubKey: false);
        if (removePreferences && Directory.Exists(places.Preferences)) { Directory.Delete(places.Preferences, true); Note("preferences and saved session deleted"); }
        else Note("preferences kept");
        Note("uninstalled");
        WriteLog();
    }
}
