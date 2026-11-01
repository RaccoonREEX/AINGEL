using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Windows.Input;
using System.Windows.Interop;

namespace Aingel.Desktop.Core;

/// <summary>AINGEL's global shortcuts, all Ctrl+Alt+letter. Ctrl+Alt+N (NVDA's own start shortcut) and the arrows
/// (NVDA table navigation) are left alone.</summary>
public enum Command { DescribeWindow, DescribeScreen, ReadFocus, AskAboutWindow, MoreDetail, StopSpeech, ShowHide, OpenDocument }

public sealed class Hotkeys : IDisposable
{
    const int WmHotkey = 0x0312;
    const uint ModAlt = 0x1, ModControl = 0x2, ModNoRepeat = 0x4000;

    public static readonly IReadOnlyDictionary<Command, Key> Keys = new Dictionary<Command, Key>
    {
        [Command.DescribeWindow] = Key.D,
        [Command.DescribeScreen] = Key.P,
        [Command.ReadFocus] = Key.F,
        [Command.AskAboutWindow] = Key.Q,
        [Command.MoreDetail] = Key.M,
        [Command.StopSpeech] = Key.S,
        [Command.ShowHide] = Key.A,
        [Command.OpenDocument] = Key.O,
    };

    [DllImport("user32.dll", SetLastError = true)] static extern bool RegisterHotKey(IntPtr hwnd, int id, uint modifiers, uint vk);
    [DllImport("user32.dll")] static extern bool UnregisterHotKey(IntPtr hwnd, int id);

    readonly HwndSource source;
    readonly Action<Command> onCommand;
    readonly List<int> registered = new();

    /// <summary>Registers every shortcut on [window]; [Failed] lists those another program already uses.</summary>
    public Hotkeys(HwndSource source, Action<Command> onCommand)
    {
        this.source = source;
        this.onCommand = onCommand;
        source.AddHook(Hook);
        foreach (var (command, key) in Keys)
        {
            var id = (int)command + 1;
            if (RegisterHotKey(source.Handle, id, ModControl | ModAlt | ModNoRepeat, (uint)KeyInterop.VirtualKeyFromKey(key))) registered.Add(id);
            else Failed.Add(command);
        }
    }

    public List<Command> Failed { get; } = new();

    public static string Label(Command command) => "Ctrl+Alt+" + Keys[command];

    IntPtr Hook(IntPtr hwnd, int message, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (message == WmHotkey && registered.Contains(wParam.ToInt32()))
        {
            handled = true;
            onCommand((Command)(wParam.ToInt32() - 1));
        }
        return IntPtr.Zero;
    }

    public void Dispose()
    {
        foreach (var id in registered) UnregisterHotKey(source.Handle, id);
        registered.Clear();
        source.RemoveHook(Hook);
    }
}
