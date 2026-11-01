using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Aingel.Desktop.Core;

namespace Aingel.Desktop.Tests;

/// <summary>Checks for system-audio captions (phase 4).</summary>
static class AudioChecks
{
    public static void Run(Action<bool, string> check)
    {
        // 1 s of a 440 Hz tone, 48 kHz stereo float (the usual Windows mix format) → 24 kHz mono 16-bit.
        var format = new AudioFormat(48000, 2, 32, true);
        var input = new byte[48000 * format.BlockAlign];
        for (var i = 0; i < 48000; i++)
        {
            var value = (float)(0.5 * Math.Sin(2 * Math.PI * 440 * i / 48000));
            BitConverter.TryWriteBytes(input.AsSpan(i * 8, 4), value);
            BitConverter.TryWriteBytes(input.AsSpan(i * 8 + 4, 4), value);
        }
        var output = new List<short>();
        var converter = new PcmConverter(format);
        // In uneven chunks, as WASAPI delivers them: the result must not depend on the chunking.
        foreach (var (start, count) in new[] { (0, 4410), (4410, 1), (4411, 20000), (24411, 23589) })
            converter.Convert(input.AsSpan(start * format.BlockAlign, count * format.BlockAlign), count, output);
        check(Math.Abs(output.Count - 24000) <= 1, $"1 s becomes 24 000 samples ({output.Count})");
        var peak = output.Max(s => Math.Abs((int)s));
        check(peak is > 15000 and < 17000, $"amplitude kept ({peak})");
        var crossings = output.Zip(output.Skip(1)).Count(pair => pair.First < 0 && pair.Second >= 0);
        check(Math.Abs(crossings - 440) <= 2, $"pitch kept ({crossings} cycles)");

        var pcm16 = new PcmConverter(new AudioFormat(24000, 1, 16, false));
        var same = new List<short>();
        pcm16.Convert(new byte[] { 0x00, 0x40, 0x00, 0xC0, 0xFF, 0x7F }, 3, same);
        check(same.SequenceEqual(new short[] { 16384, -16384, 32767 }), "24 kHz mono 16-bit passes through unchanged");
        check(Throws(() => new PcmConverter(new AudioFormat(48000, 2, 8, false))), "8-bit audio refused");

        // WAVEFORMATEXTENSIBLE with the float subtype, as GetMixFormat returns it.
        var raw = new byte[40];
        BitConverter.TryWriteBytes(raw.AsSpan(0, 2), (ushort)0xFFFE);
        BitConverter.TryWriteBytes(raw.AsSpan(2, 2), (ushort)2);
        BitConverter.TryWriteBytes(raw.AsSpan(4, 4), 48000);
        BitConverter.TryWriteBytes(raw.AsSpan(14, 2), (ushort)32);
        BitConverter.TryWriteBytes(raw.AsSpan(16, 2), (ushort)22);
        new Guid("00000003-0000-0010-8000-00aa00389b71").TryWriteBytes(raw.AsSpan(24, 16));
        check(LoopbackCapture.ParseFormat(raw) == new AudioFormat(48000, 2, 32, true), "extensible float mix format");

        var own = new Profile("p1", "Mary", "es-EC", "owner", "self");
        using (var start = JsonDocument.Parse(CaptionsClient.StartMessage(own, false)))
        {
            var root = start.RootElement;
            check(root.GetProperty("type").GetString() == "start" && root.GetProperty("profile").GetString() == "p1"
                  && !root.TryGetProperty("private_test", out _) && !root.TryGetProperty("synthetic", out _), "start message without declaration");
            check(root.GetProperty("source").GetString() == "system", "the computer's audio is declared as such (meeting audio purpose)");
        }
        check(CaptionsClient.StartMessage(own, true).Contains("\"private_test\":true"), "private test only when chosen");
        check(Throws(() => CaptionsClient.StartMessage(own with { Role = "caregiver" }, true)), "private test only on the own profile");
        check(CaptionsClient.Endpoint(new Uri("https://aingel.mapatechstudio.com/")).ToString() == "wss://aingel.mapatechstudio.com/ws/captions/", "secure WebSocket for HTTPS");
        check(CaptionsClient.Endpoint(new Uri("http://127.0.0.1:8010/")).ToString() == "ws://127.0.0.1:8010/ws/captions/", "local WebSocket");
        CaptionEvent? Parse(string json) { using var d = JsonDocument.Parse(json); return CaptionsClient.Parse(d.RootElement); }
        check(Parse("{\"type\":\"transcript\",\"turnId\":3,\"transcript\":\"Buenos días\",\"final\":true}") == new CaptionEvent("transcript", "3", "Buenos días", true, null), "final transcript");
        check(Parse("{\"type\":\"speaker\",\"turnId\":3,\"label\":\"1\"}")?.Speaker == "1", "speaker label only when reported");
        check(Parse("{\"type\":\"speechStart\"}") == null, "nothing to show");

        // As seen live: cumulative partials, then «speechComplete», then a final event with no text.
        var assembler = new CaptionAssembler();
        check(assembler.Feed(new CaptionEvent("transcript", "1", "Buenos", false, null)) == ("Buenos", null), "partial shown");
        assembler.Feed(new CaptionEvent("transcript", "1", "Buenos días a todos.", false, null));
        check(assembler.Feed(new CaptionEvent("speechComplete", "1", "", true, null)).Final == "Buenos días a todos.", "turn ends with its last partial");
        check(assembler.Feed(new CaptionEvent("transcript", "1", "", true, null)).Final == null, "a line is emitted once");
        assembler.Feed(new CaptionEvent("transcript", "2", "Empezamos", false, null));
        check(assembler.Feed(new CaptionEvent("transcript", "2", "Empezamos la reunión.", true, null)).Final == "Empezamos la reunión.", "final text wins");
        check(assembler.Speaker("2") == null, "no speaker unless reported");
        assembler.Feed(new CaptionEvent("speaker", "3", "", false, "1"));
        check(assembler.Speaker("3") == "1", "reported speaker kept for its turn");

        // A real loopback capture for about 1.2 s: frames of exactly 200 ms, at real-time pace (silence when nothing plays).
        var frames = new List<byte[]>();
        try
        {
            using var capture = new LoopbackCapture();
            capture.Start(frame => { lock (frames) frames.Add(frame); });
            Thread.Sleep(1250);
            capture.Stop();
            check(capture.Format != null, $"mix format read ({capture.Format})");
            lock (frames)
            {
                check(frames.Count is >= 4 and <= 7, $"real-time frames ({frames.Count})");
                check(frames.All(f => f.Length == 9600), "200 ms frames of 9600 bytes");
            }
        }
        catch (ApiFailure failure) { check(false, "loopback capture: " + failure.Code); }
    }

    static bool Throws(Action action)
    {
        try { action(); return false; } catch (Exception e) when (e is ApiFailure or NotSupportedException) { return true; }
    }

    /// <summary>Test G: a synthetic meeting read by a Windows voice (no real person), streamed in real time to the
    /// captions server, which sends it to Meta. Only with AINGEL_TEST_CAPTIONS=1 and a server that allows it.</summary>
    public static async Task<List<string>> SyntheticMeeting(ApiClient api, Profile profile, bool privateTest, string text)
    {
        var wav = Path.Combine(Path.GetTempPath(), "aingel-synthetic-meeting.wav");
        Synthesize(text, wav);
        var pcm = Data(File.ReadAllBytes(wav));
        File.Delete(wav);
        var finals = new List<string>();
        var ended = new TaskCompletionSource<string?>();
        await using var client = new CaptionsClient();
        var assembler = new CaptionAssembler();
        var events = 0;
        client.Caption += caption =>
        {
            lock (finals)
            {
                events++;
                if (assembler.Feed(caption).Final is { } line) finals.Add(line);
            }
        };
        client.Ended += reason => ended.TrySetResult(reason);
        await client.Start(api, profile, privateTest);
        var silence = new byte[LoopbackCapture.FrameSamples * 2 * 8];  // 1.6 s after the speech: the last sentence ends
        var all = pcm.Concat(silence).ToArray();
        for (var offset = 0; offset < all.Length; offset += 9600)
        {
            var frame = all.AsSpan(offset, Math.Min(9600, all.Length - offset)).ToArray();
            if (frame.Length % 2 == 1) frame = frame[..^1];
            if (!await client.SendAudio(frame)) break;
            await Task.Delay(200);
        }
        await client.Stop();
        await Task.WhenAny(ended.Task, Task.Delay(30_000));
        Console.WriteLine($"audio: {pcm.Length / 48000.0:F1} s of synthetic speech, peak {Peak(pcm)}; {events} events");
        if (ended.Task.IsCompleted && ended.Task.Result is { } reason) throw new ApiFailure(reason);
        return finals;
    }

    static void Synthesize(string text, string path)
    {
        dynamic stream = Activator.CreateInstance(Type.GetTypeFromProgID("SAPI.SpFileStream")!)!;
        dynamic format = Activator.CreateInstance(Type.GetTypeFromProgID("SAPI.SpAudioFormat")!)!;
        format.Type = 26;  // SAFT24kHz16BitMono
        stream.Format = format;
        stream.Open(path, 3, false);
        dynamic voice = Activator.CreateInstance(Type.GetTypeFromProgID("SAPI.SpVoice")!)!;
        var voices = voice.GetVoices();
        for (var i = 0; i < (int)voices.Count; i++)
            if (Speech.PrimaryLanguage((string)voices.Item(i).GetAttribute("Language")) == 0x0A) { voice.Voice = voices.Item(i); break; }
        voice.AudioOutputStream = stream;
        voice.Speak(text, 0);
        stream.Close();
    }

    static int Peak(byte[] pcm)
    {
        var peak = 0;
        for (var i = 0; i + 1 < pcm.Length; i += 2) peak = Math.Max(peak, Math.Abs((int)BitConverter.ToInt16(pcm, i)));
        return peak;
    }

    /// <summary>The «data» chunk of a WAV file.</summary>
    internal static byte[] Data(byte[] wav)
    {
        for (var offset = 12; offset + 8 <= wav.Length;)
        {
            var id = Encoding.ASCII.GetString(wav, offset, 4);
            var size = BitConverter.ToInt32(wav, offset + 4);
            if (id == "data") return wav.AsSpan(offset + 8, Math.Min(size, wav.Length - offset - 8)).ToArray();
            offset += 8 + size + (size & 1);
        }
        throw new InvalidDataException("no data chunk");
    }
}
