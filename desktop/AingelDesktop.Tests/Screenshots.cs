using System;
using System.IO;
using System.Threading;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Aingel.Desktop.Core;

namespace Aingel.Desktop.Tests;

/// <summary>
/// Renders AINGEL Desktop's real windows to PNG for the website (`--screenshots <folder>`). The windows are built by
/// the app's own code and drawn offscreen: nothing is captured from the screen and no account is used.
/// </summary>
static class Screenshots
{
    public static void Run(string folder)
    {
        Directory.CreateDirectory(folder);
        var thread = new Thread(() =>
        {
            var app = new App();
            app.InitializeComponent();
            app.Connect(Backend.Default);
            var profile = new Profile("example", "Ejemplo", "es-EC", "owner", "self");
            Save(new MainWindow(app, profile), 400, 760, Path.Combine(folder, "desktop-main.png"));
            Save(new CaptionsWindow(app, profile), 720, 520, Path.Combine(folder, "desktop-captions.png"));
            Save(new LoginWindow(app), 420, 520, Path.Combine(folder, "desktop-sign-in.png"));
            app.Shutdown();
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
    }

    static void Save(Window window, int width, int height, string path)
    {
        var content = (FrameworkElement)window.Content;
        window.Content = null;  // drawn on its own, at the window's size, with the window's background
        var host = new System.Windows.Controls.Border { Background = Brushes.White, Child = content, Width = width, Height = height };
        host.Measure(new Size(width, height));
        host.Arrange(new Rect(0, 0, width, height));
        host.UpdateLayout();
        var bitmap = new RenderTargetBitmap(width * 2, height * 2, 192, 192, PixelFormats.Pbgra32);
        bitmap.Render(host);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(bitmap));
        using var stream = File.Create(path);
        encoder.Save(stream);
        window.Close();
    }
}
