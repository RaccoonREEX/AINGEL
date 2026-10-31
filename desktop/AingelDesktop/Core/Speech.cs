using System;
using System.Globalization;
using System.Runtime.InteropServices;

namespace Aingel.Desktop.Core;

/// <summary>
/// AINGEL's voice through the Windows speech engine (SAPI, built into Windows), with a voice of the profile's
/// language when one is installed. With a screen reader running, AINGEL stays quiet by default and the answer is
/// announced by the screen reader instead (see MainWindow), so the two voices never overlap.
/// </summary>
public sealed class Speech : IDisposable
{
    const int Async = 1, Purge = 2;
    const uint SpiGetScreenReader = 0x0046;
    dynamic? voice;

    [DllImport("user32.dll", SetLastError = true)]
    static extern bool SystemParametersInfo(uint action, uint param, ref bool value, uint winIni);

    public Speech(string locale)
    {
        try
        {
            var type = Type.GetTypeFromProgID("SAPI.SpVoice");
            if (type == null) return;
            voice = Activator.CreateInstance(type);
            var wanted = LanguageOf(locale);
            var voices = voice!.GetVoices();
            for (var i = 0; i < (int)voices.Count; i++)
            {
                var token = voices.Item(i);
                if (PrimaryLanguage((string)token.GetAttribute("Language")) == wanted) { voice.Voice = token; break; }
            }
        }
        catch (COMException) { voice = null; }
    }

    public bool Available => voice != null;

    /// <summary>Windows reports a screen reader (NVDA, JAWS, Narrator) running.</summary>
    public static bool ScreenReaderRunning()
    {
        var running = false;
        return SystemParametersInfo(SpiGetScreenReader, 0, ref running, 0) && running;
    }

    public void Speak(string text)
    {
        var current = voice;
        if (current is null || string.IsNullOrWhiteSpace(text)) return;
        try { current.Speak(text, Async | Purge); } catch (COMException) { }
    }

    public void Stop()
    {
        var current = voice;
        if (current is null) return;
        try { current.Speak("", Async | Purge); } catch (COMException) { }
    }

    /// <summary>The primary language id (LANGID &amp; 0x3FF) of a culture: 0x0A Spanish, 0x09 English.</summary>
    internal static int LanguageOf(string locale) =>
        locale.StartsWith("es", StringComparison.OrdinalIgnoreCase) ? 0x0A : 0x09;

    /// <summary>The primary language of a SAPI voice's «Language» attribute ("C0A", or "409;9"), or -1.</summary>
    internal static int PrimaryLanguage(string? attribute)
    {
        var first = (attribute ?? "").Split(';')[0].Trim();
        return int.TryParse(first, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var id) ? id & 0x3FF : -1;
    }

    public void Dispose() { Stop(); voice = null; }
}
