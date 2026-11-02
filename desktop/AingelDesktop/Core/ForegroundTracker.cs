using System;
using System.Runtime.InteropServices;

namespace Aingel.Desktop.Core;

/// <summary>
/// Remembers the last window the person used outside AINGEL, so «describe the active window» from AINGEL's own button
/// means the window they were working in, not AINGEL. Only the window handle is kept; nothing is captured here.
/// </summary>
public sealed class ForegroundTracker : IDisposable
{
    const uint EventSystemForeground = 0x0003, WinEventOutOfContext = 0x0000;
    delegate void WinEventProc(IntPtr hook, uint type, IntPtr hwnd, int idObject, int idChild, uint thread, uint time);

    [DllImport("user32.dll")] static extern IntPtr SetWinEventHook(uint min, uint max, IntPtr module, WinEventProc proc, uint process, uint thread, uint flags);
    [DllImport("user32.dll")] static extern bool UnhookWinEvent(IntPtr hook);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint process);

    readonly WinEventProc callback;  // kept alive: the system calls it later
    readonly IntPtr hook;
    readonly uint ownProcess = (uint)Environment.ProcessId;

    public IntPtr Last { get; private set; }

    public ForegroundTracker()
    {
        callback = (_, _, hwnd, _, _, _, _) => Remember(hwnd);
        hook = SetWinEventHook(EventSystemForeground, EventSystemForeground, IntPtr.Zero, callback, 0, 0, WinEventOutOfContext);
        Remember(ScreenCapture.Foreground());
    }

    void Remember(IntPtr hwnd)
    {
        if (hwnd == IntPtr.Zero) return;
        GetWindowThreadProcessId(hwnd, out var process);
        if (process != ownProcess) Last = hwnd;
    }

    /// <summary>The window to describe: the foreground one unless it is AINGEL's, then the last one used before.</summary>
    public IntPtr Target()
    {
        var now = ScreenCapture.Foreground();
        GetWindowThreadProcessId(now, out var process);
        return process != ownProcess && now != IntPtr.Zero ? now : Last;
    }

    public void Dispose() { if (hook != IntPtr.Zero) UnhookWinEvent(hook); }
}
