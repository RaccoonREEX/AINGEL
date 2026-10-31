using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

namespace Aingel.Desktop.Core;

/// <summary>One picture of a window or a monitor, ready to send.</summary>
public sealed record Shot(byte[] Jpeg, string Title, int Width, int Height);

/// <summary>
/// One-off captures, only when the person asks (a button or a shortcut): never in the background. It reads what the
/// screen shows through GDI, so windows that protect their content (DRM video, windows excluded from capture) come
/// out black or missing: AINGEL never works around that. AINGEL's own window is excluded from every capture.
/// </summary>
public static class ScreenCapture
{
    const uint WdaExcludeFromCapture = 0x11;
    const int DwmwaExtendedFrameBounds = 9;

    [StructLayout(LayoutKind.Sequential)]
    struct Rect { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int max);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hwnd, out Rect rect);
    [DllImport("user32.dll")] static extern bool SetWindowDisplayAffinity(IntPtr hwnd, uint affinity);
    [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr hwnd, int attribute, out Rect value, int size);
    [DllImport("user32.dll")] static extern IntPtr GetDC(IntPtr hwnd);
    [DllImport("user32.dll")] static extern int ReleaseDC(IntPtr hwnd, IntPtr dc);
    [DllImport("gdi32.dll")] static extern bool BitBlt(IntPtr dest, int x, int y, int width, int height, IntPtr source, int sourceX, int sourceY, int operation);
    // CAPTUREBLT also copies layered (translucent) windows; Graphics.CopyFromScreen does not accept it.
    const int SrcCopy = 0x00CC0020, CaptureBlt = 0x40000000;

    public static IntPtr Foreground() => GetForegroundWindow();

    public static string Title(IntPtr hwnd)
    {
        var text = new StringBuilder(512);
        GetWindowText(hwnd, text, text.Capacity);
        return text.ToString();
    }

    /// <summary>Keeps [hwnd] (AINGEL's window) out of every screen capture, AINGEL's own included.</summary>
    public static bool ExcludeFromCapture(IntPtr hwnd) => SetWindowDisplayAffinity(hwnd, WdaExcludeFromCapture);

    /// <summary>The visible bounds of [hwnd] in physical pixels, or null when minimized or hidden.</summary>
    public static Rectangle? Bounds(IntPtr hwnd)
    {
        if (hwnd == IntPtr.Zero || IsIconic(hwnd) || !IsWindowVisible(hwnd)) return null;
        // The frame without the invisible resize borders of Windows 10/11.
        if (DwmGetWindowAttribute(hwnd, DwmwaExtendedFrameBounds, out var frame, Marshal.SizeOf<Rect>()) != 0 && !GetWindowRect(hwnd, out frame)) return null;
        var bounds = Rectangle.FromLTRB(frame.Left, frame.Top, frame.Right, frame.Bottom);
        bounds.Intersect(SystemInformation.VirtualScreen);
        return bounds.Width > 8 && bounds.Height > 8 ? bounds : null;
    }

    /// <summary>The window [hwnd] as it is on screen now.</summary>
    public static Shot Window(IntPtr hwnd) =>
        Area(Bounds(hwnd) ?? throw new ApiFailure("window_not_visible"), Title(hwnd));

    /// <summary>The whole monitor that shows [hwnd] (the primary one when none).</summary>
    public static Shot Monitor(IntPtr hwnd)
    {
        var screen = hwnd == IntPtr.Zero ? Screen.PrimaryScreen! : Screen.FromHandle(hwnd);
        return Area(screen.Bounds, Title(hwnd));
    }

    static Shot Area(Rectangle area, string title)
    {
        using var bitmap = new Bitmap(area.Width, area.Height, PixelFormat.Format24bppRgb);
        using (var graphics = Graphics.FromImage(bitmap))
        {
            var target = graphics.GetHdc();
            var screen = GetDC(IntPtr.Zero);
            try
            {
                if (!BitBlt(target, 0, 0, area.Width, area.Height, screen, area.X, area.Y, SrcCopy | CaptureBlt)) throw new ApiFailure("capture_failed");
            }
            finally
            {
                ReleaseDC(IntPtr.Zero, screen);
                graphics.ReleaseHdc(target);
            }
        }
        return new Shot(Jpeg(bitmap), title, area.Width, area.Height);
    }

    /// <summary>JPEG at most [maxSide] pixels on its longer side (the server's own limit is 2048).</summary>
    internal static byte[] Jpeg(Bitmap source, int maxSide = 2048, long quality = 88)
    {
        var scale = Math.Min(1.0, maxSide / (double)Math.Max(source.Width, source.Height));
        using var resized = new Bitmap(Math.Max(1, (int)Math.Round(source.Width * scale)), Math.Max(1, (int)Math.Round(source.Height * scale)), PixelFormat.Format24bppRgb);
        using (var graphics = Graphics.FromImage(resized))
        {
            graphics.InterpolationMode = InterpolationMode.HighQualityBicubic;
            graphics.DrawImage(source, 0, 0, resized.Width, resized.Height);
        }
        var codec = ImageCodecInfo.GetImageEncoders().First(c => c.FormatID == ImageFormat.Jpeg.Guid);
        using var parameters = new EncoderParameters(1);
        parameters.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, quality);
        using var output = new MemoryStream();
        resized.Save(output, codec, parameters);
        return output.ToArray();
    }
}
