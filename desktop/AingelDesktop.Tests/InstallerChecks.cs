using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using Aingel.Setup;
using Microsoft.Win32;

namespace Aingel.Desktop.Tests;

/// <summary>Checks for the installer (phase 6), in a temporary folder and a test registry key.</summary>
static class InstallerChecks
{
    public static void Run(Action<bool, string> check)
    {
        check(Installer.Requirements(new Version(10, 0, 26100), 1L << 30, false).Count == 0, "Windows 11 passes");
        check(Installer.Requirements(new Version(10, 0, 18363), 1L << 30, false).Contains("windows_too_old"), "Windows 10 1909 refused");
        check(Installer.Requirements(new Version(10, 0, 22631), 10_000, true) is { Count: 2 } problems && problems.Contains("disk_space") && problems.Contains("app_running"), "space and running app reported");

        var root = Path.Combine(Path.GetTempPath(), "aingel-setup-test-" + Guid.NewGuid().ToString("N"));
        var places = new Places(Path.Combine(root, "Programs", "AINGEL Desktop"), Path.Combine(root, "StartMenu"), Path.Combine(root, "Desktop"),
            Path.Combine(root, "Data"), @"Software\AINGEL-Test\Uninstall\" + Guid.NewGuid().ToString("N"));
        var setup = Path.Combine(root, "setup.exe");
        try
        {
            Directory.CreateDirectory(root);
            File.WriteAllBytes(setup, new byte[] { 1, 2, 3 });
            var installer = new Installer(places);
            check(Failure(() => installer.Install(Zip(("readme.txt", "x")), setup, false, "0.1.0")) == "payload_damaged", "payload without the app refused");
            check(Failure(() => installer.Install(Zip(("../evil.txt", "x"), ("AingelDesktop.exe", "x")), setup, false, "0.1.0")) == "payload_damaged", "zip entry outside the folder refused");
            check(!File.Exists(Path.Combine(root, "Programs", "evil.txt")), "nothing written outside");

            installer.Install(Zip(("AingelDesktop.exe", "v1"), ("AingelDesktop.dll", "v1")), setup, true, "0.1.0");
            check(File.ReadAllText(places.AppExe) == "v1" && File.Exists(places.Uninstaller), "program and uninstaller installed");
            check(File.Exists(places.StartMenuShortcut) && File.Exists(places.DesktopShortcut), "shortcuts created");
            using (var key = Registry.CurrentUser.OpenSubKey(places.UninstallKey))
                check(key?.GetValue("DisplayVersion") as string == "0.1.0" && key.GetValue("Publisher") as string == Installer.Publisher, "registered with version and publisher");
            check(installer.InstalledVersion() == "0.1.0", "installed version read back");

            Directory.CreateDirectory(places.Preferences);
            File.WriteAllText(Path.Combine(places.Preferences, "settings.json"), "{}");
            installer.Install(Zip(("AingelDesktop.exe", "v2")), setup, false, "0.2.0");
            check(File.ReadAllText(places.AppExe) == "v2" && !File.Exists(Path.Combine(places.InstallDir, "AingelDesktop.dll")), "upgrade replaces the program files");
            check(File.Exists(Path.Combine(places.Preferences, "settings.json")), "upgrade keeps preferences");
            check(!File.Exists(places.DesktopShortcut), "desktop shortcut follows the choice");
            check(installer.InstalledVersion() == "0.2.0", "upgrade registered");

            var log = File.ReadAllText(places.Log);
            check(log.Contains("0.2.0") && !log.Contains("password", StringComparison.OrdinalIgnoreCase), "log without secrets");

            installer.Uninstall(removePreferences: false);
            check(!Directory.Exists(places.InstallDir) && !File.Exists(places.StartMenuShortcut) && installer.InstalledVersion() == null, "uninstalled");
            check(File.Exists(Path.Combine(places.Preferences, "settings.json")), "uninstall keeps preferences by default");
            installer.Install(Zip(("AingelDesktop.exe", "v3")), setup, false, "0.3.0");
            installer.Uninstall(removePreferences: true);
            check(!Directory.Exists(places.Preferences), "preferences removed when chosen");
        }
        finally
        {
            Registry.CurrentUser.DeleteSubKeyTree(@"Software\AINGEL-Test", throwOnMissingSubKey: false);
            if (Directory.Exists(root)) Directory.Delete(root, true);
        }
    }

    static byte[] Zip(params (string Name, string Text)[] entries)
    {
        using var buffer = new MemoryStream();
        using (var archive = new ZipArchive(buffer, ZipArchiveMode.Create, leaveOpen: true))
            foreach (var (name, text) in entries)
            {
                using var writer = new StreamWriter(archive.CreateEntry(name).Open());
                writer.Write(text);
            }
        return buffer.ToArray();
    }

    static string? Failure(Action action)
    {
        try { action(); return null; } catch (SetupFailure failure) { return failure.Code; }
    }
}
