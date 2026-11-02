using System;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows;
using System.Windows.Interop;
using Aingel.Desktop.Core;

namespace Aingel.Desktop.Tests;

static class PrivacyChecks
{
    [DllImport("user32.dll")]
    static extern bool GetWindowDisplayAffinity(IntPtr hwnd, out uint affinity);

    internal static void Run(Action<bool, string> check)
    {
        bool firstProtected = false, secondProtected = false;
        Exception? error = null;
        var thread = new Thread(() =>
        {
            try
            {
                var app = new Application { ShutdownMode = ShutdownMode.OnExplicitShutdown };
                var first = new Window { Title = "AINGEL privacy test", Width = 180, Height = 100, ShowInTaskbar = false };
                var second = new Window { Title = "AINGEL privacy test 2", Width = 180, Height = 100, ShowInTaskbar = false };
                first.Show();
                second.Show();
                ScreenCapture.ExcludeOwnWindows();
                firstProtected = GetWindowDisplayAffinity(new WindowInteropHelper(first).Handle, out var a) && a == 0x11;
                secondProtected = GetWindowDisplayAffinity(new WindowInteropHelper(second).Handle, out var b) && b == 0x11;
                first.Close();
                second.Close();
                app.Shutdown();
            }
            catch (Exception failure) { error = failure; }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        check(error == null && firstProtected && secondProtected, "all visible application windows excluded from capture");
        var refused = false;
        try { ScreenCapture.RequireExclusion(IntPtr.Zero); }
        catch (ApiFailure failure) { refused = failure.Code == "capture_failed"; }
        check(refused, "capture is refused when a window cannot be protected");
    }
}
