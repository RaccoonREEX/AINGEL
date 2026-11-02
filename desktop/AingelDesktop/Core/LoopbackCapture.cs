using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;

namespace Aingel.Desktop.Core;

/// <summary>
/// What this computer is playing (meetings, videos), captured with WASAPI loopback from the default output device —
/// the same audio that goes to the speakers, never the microphone. Only while the person keeps captions on.
/// Audio is converted to 24 kHz mono PCM and handed out in 200 ms frames; when nothing plays, silence keeps time
/// moving so the transcription can finish a sentence. The COM interfaces are declared here (no NuGet package).
/// </summary>
public sealed class LoopbackCapture : IDisposable
{
    public const int FrameSamples = PcmConverter.TargetRate / 5;  // 200 ms: the server accepts at most 9600 bytes
    const int ClsctxAll = 23, StreamFlagsLoopback = 0x00020000, BufferFlagsSilent = 0x2;
    const long BufferDuration = 10_000_000;  // 1 s, in 100 ns units

    enum DataFlow { Render, Capture, All }
    enum Role { Console, Multimedia, Communications }

    [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    class MMDeviceEnumeratorComObject { }

    [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDeviceEnumerator
    {
        int EnumAudioEndpoints(DataFlow flow, int mask, out IntPtr devices);
        int GetDefaultAudioEndpoint(DataFlow flow, Role role, out IMMDevice device);
    }

    [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDevice
    {
        int Activate(ref Guid iid, int context, IntPtr parameters, [MarshalAs(UnmanagedType.IUnknown)] out object client);
    }

    [ComImport, Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioClient
    {
        int Initialize(int shareMode, int streamFlags, long bufferDuration, long periodicity, IntPtr format, IntPtr session);
        int GetBufferSize(out uint frames);
        int GetStreamLatency(out long latency);
        int GetCurrentPadding(out uint frames);
        int IsFormatSupported(int shareMode, IntPtr format, out IntPtr closest);
        int GetMixFormat(out IntPtr format);
        int GetDevicePeriod(out long defaultPeriod, out long minimumPeriod);
        int Start();
        int Stop();
        int Reset();
        int SetEventHandle(IntPtr handle);
        int GetService(ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object service);
    }

    [ComImport, Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioCaptureClient
    {
        int GetBuffer(out IntPtr data, out uint frames, out uint flags, out ulong devicePosition, out ulong qpcPosition);
        int ReleaseBuffer(uint frames);
        int GetNextPacketSize(out uint frames);
    }

    static readonly Guid FloatSubtype = new("00000003-0000-0010-8000-00aa00389b71");
    static readonly Guid PcmSubtype = new("00000001-0000-0010-8000-00aa00389b71");

    IAudioClient? client;
    IAudioCaptureClient? capture;
    PcmConverter? converter;
    AudioFormat? format;
    CancellationTokenSource? stop;
    Task? loop;

    public AudioFormat? Format => format;

    /// <summary>Reads a WAVEFORMATEX / WAVEFORMATEXTENSIBLE structure.</summary>
    internal static AudioFormat ParseFormat(byte[] raw)
    {
        var tag = BitConverter.ToUInt16(raw, 0);
        var channels = BitConverter.ToUInt16(raw, 2);
        var rate = BitConverter.ToInt32(raw, 4);
        var bits = BitConverter.ToUInt16(raw, 14);
        var isFloat = tag == 3;
        if (tag == 0xFFFE && raw.Length >= 40)
        {
            var subtype = new Guid(raw.AsSpan(24, 16));
            if (subtype == FloatSubtype) isFloat = true;
            else if (subtype != PcmSubtype) throw new NotSupportedException("audio_format_unsupported");
        }
        else if (tag != 1 && tag != 3) throw new NotSupportedException("audio_format_unsupported");
        return new AudioFormat(rate, channels, bits, isFloat);
    }

    /// <summary>Whether Windows has a default audio output to capture (none on a machine without speakers or with all
    /// outputs disabled).</summary>
    public static bool HasOutputDevice()
    {
        try
        {
            var enumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
            return enumerator.GetDefaultAudioEndpoint(DataFlow.Render, Role.Console, out _) == 0;
        }
        catch (COMException) { return false; }
    }

    /// <summary>Starts capturing; [onFrame] receives each 200 ms frame (16-bit PCM bytes) on a background thread. A
    /// missing or unusable output device is reported as ApiFailure("system_audio_unavailable"), never as a crash: the
    /// COM interop raises COMException for some failures before Check sees their HRESULT.</summary>
    public void Start(Action<byte[]> onFrame)
    {
        try { Open(); }
        catch (COMException) { throw new ApiFailure("system_audio_unavailable"); }
        catch (InvalidCastException) { throw new ApiFailure("system_audio_unavailable"); }
        stop = new CancellationTokenSource();
        var token = stop.Token;
        loop = Task.Run(() => Run(onFrame, token), token);
    }

    void Open()
    {
        var enumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
        Check(enumerator.GetDefaultAudioEndpoint(DataFlow.Render, Role.Console, out var device));
        var audioClientId = typeof(IAudioClient).GUID;
        Check(device.Activate(ref audioClientId, ClsctxAll, IntPtr.Zero, out var activated));
        client = (IAudioClient)activated;
        Check(client.GetMixFormat(out var mix));
        try
        {
            var size = 18 + Marshal.ReadInt16(mix, 16);
            var raw = new byte[Math.Max(size, 18)];
            Marshal.Copy(mix, raw, 0, raw.Length);
            format = ParseFormat(raw);
            converter = new PcmConverter(format);
            Check(client.Initialize(0, StreamFlagsLoopback, BufferDuration, 0, mix, IntPtr.Zero));
        }
        finally { Marshal.FreeCoTaskMem(mix); }
        var captureId = typeof(IAudioCaptureClient).GUID;
        Check(client.GetService(ref captureId, out var service));
        capture = (IAudioCaptureClient)service;
        Check(client.Start());
    }

    void Run(Action<byte[]> onFrame, CancellationToken token)
    {
        var pending = new List<short>(FrameSamples * 4);
        var clock = Stopwatch.StartNew();
        long produced = 0;
        while (!token.IsCancellationRequested)
        {
            Thread.Sleep(20);
            while (capture!.GetNextPacketSize(out var packet) == 0 && packet > 0)
            {
                if (capture.GetBuffer(out var data, out var frames, out var flags, out _, out _) != 0) break;
                var before = pending.Count;
                if ((flags & BufferFlagsSilent) != 0 || data == IntPtr.Zero)
                    PcmConverter.Silence((int)Math.Round(frames * (double)PcmConverter.TargetRate / format!.SampleRate), pending);
                else
                {
                    var bytes = new byte[frames * format!.BlockAlign];
                    Marshal.Copy(data, bytes, 0, bytes.Length);
                    converter!.Convert(bytes, (int)frames, pending);
                }
                produced += pending.Count - before;
                capture.ReleaseBuffer(frames);
            }
            // Loopback delivers nothing while nothing plays: fill with silence up to now, never ahead of real time.
            var expected = (long)(clock.Elapsed.TotalSeconds * PcmConverter.TargetRate);
            if (expected - produced > FrameSamples / 2)
            {
                var gap = (int)(expected - produced);
                PcmConverter.Silence(gap, pending);
                produced += gap;
            }
            while (pending.Count >= FrameSamples)
            {
                var frame = new byte[FrameSamples * 2];
                for (var i = 0; i < FrameSamples; i++) BitConverter.TryWriteBytes(frame.AsSpan(i * 2, 2), pending[i]);
                pending.RemoveRange(0, FrameSamples);
                onFrame(frame);
            }
        }
    }

    static void Check(int result)
    {
        if (result != 0) throw new ApiFailure("system_audio_unavailable");
    }

    public void Stop()
    {
        stop?.Cancel();
        try { loop?.Wait(1000); } catch (AggregateException) { }
        try { client?.Stop(); } catch (COMException) { }
        stop = null;
        loop = null;
    }

    public void Dispose()
    {
        Stop();
        if (capture != null) Marshal.ReleaseComObject(capture);
        if (client != null) Marshal.ReleaseComObject(client);
        capture = null;
        client = null;
    }
}
