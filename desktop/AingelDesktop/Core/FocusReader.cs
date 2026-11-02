using System;
using System.Windows.Automation;

namespace Aingel.Desktop.Core;

/// <summary>
/// What has the keyboard focus, read locally with Windows UI Automation (the same source screen readers use).
/// Nothing is sent anywhere, and the content of password fields is never read.
/// </summary>
public static class FocusReader
{
    /// <summary>Call off the UI thread: UI Automation may wait on the other application.</summary>
    public static string Describe(string locale)
    {
        try
        {
            var element = AutomationElement.FocusedElement;
            if (element == null) return Texts.Get(locale, "focus_none");
            var current = element.Current;
            string? value = null;
            if (!current.IsPassword && element.TryGetCurrentPattern(ValuePattern.Pattern, out var pattern))
                value = ((ValuePattern)pattern).Current.Value;
            return Phrase(locale, current.Name, current.LocalizedControlType, value, current.IsPassword, ScreenCapture.Title(ScreenCapture.Foreground()));
        }
        catch (Exception e) when (e is ElementNotAvailableException or InvalidOperationException or System.Runtime.InteropServices.COMException)
        {
            return Texts.Get(locale, "focus_none");
        }
    }

    internal static string Phrase(string locale, string? name, string? type, string? value, bool isPassword, string? window)
    {
        var es = locale.StartsWith("es", StringComparison.OrdinalIgnoreCase);
        var kind = string.IsNullOrWhiteSpace(type) ? (es ? "Elemento" : "Element") : char.ToUpper(type[0]) + type[1..];
        var phrase = string.IsNullOrWhiteSpace(name) ? kind + (es ? " sin nombre" : " without a name") : $"{kind} «{name.Trim()}»";
        if (isPassword) phrase += es ? ". Es un campo de contraseña: AINGEL no lee su contenido" : ". It is a password field: AINGEL does not read its content";
        else if (!string.IsNullOrWhiteSpace(value))
        {
            var shown = value.Trim().TrimEnd('.');
            if (shown.Length > 300) shown = shown[..300] + "…";
            phrase += (es ? ", contiene: " : ", contains: ") + shown;
        }
        if (!string.IsNullOrWhiteSpace(window)) phrase += (es ? ". Ventana: " : ". Window: ") + window.Trim();
        return phrase + ".";
    }
}
