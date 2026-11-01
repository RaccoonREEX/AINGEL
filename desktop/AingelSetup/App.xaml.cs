using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows;

namespace Aingel.Setup;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        var places = Places.ForCurrentUser();
        var uninstall = e.Args.Contains("/uninstall", StringComparer.OrdinalIgnoreCase);
        var self = Environment.ProcessPath!;
        // The uninstaller cannot delete the folder it runs from: it continues from a temporary copy, still visible.
        if (uninstall && Path.GetDirectoryName(self)!.Equals(places.InstallDir, StringComparison.OrdinalIgnoreCase))
        {
            var copy = Path.Combine(Path.GetTempPath(), $"AingelUninstall-{Guid.NewGuid():N}.exe");
            File.Copy(self, copy);
            Process.Start(new ProcessStartInfo(copy, "/uninstall") { UseShellExecute = false });
            Shutdown();
            return;
        }
        new SetupWindow(places, uninstall).Show();
    }
}
