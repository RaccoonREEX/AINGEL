using System;
using System.Collections.Generic;

namespace Aingel.Desktop.Core;

/// <summary>The layout of the audio Windows delivers (its mix format): float or integer samples, channels, rate.</summary>
public sealed record AudioFormat(int SampleRate, int Channels, int BitsPerSample, bool IsFloat)
{
    public int BlockAlign => Channels * BitsPerSample / 8;
}

/// <summary>
/// Turns Windows audio (usually 48 kHz stereo float) into what live captions take: 24 kHz, mono, 16-bit little-endian
/// PCM (backend assistance.captions). Channels are averaged; the rate is converted by linear interpolation, keeping
/// the position between chunks so there are no clicks at their edges.
/// </summary>
public sealed class PcmConverter
{
    public const int TargetRate = 24000;
    readonly AudioFormat format;
    readonly double step;
    double position;   // next output sample, in input samples from the start of the pending input
    float previous;    // the last input sample of the previous chunk (interpolation across chunks)
    bool started;

    public PcmConverter(AudioFormat format)
    {
        if (format.Channels < 1 || format.SampleRate < 8000 || format.BitsPerSample is not (16 or 24 or 32) || (format.IsFloat && format.BitsPerSample != 32))
            throw new NotSupportedException("audio_format_unsupported");
        this.format = format;
        step = format.SampleRate / (double)TargetRate;
    }

    float Sample(ReadOnlySpan<byte> data, int offset) => format switch
    {
        { IsFloat: true } => BitConverter.ToSingle(data.Slice(offset, 4)),
        { BitsPerSample: 16 } => BitConverter.ToInt16(data.Slice(offset, 2)) / 32768f,
        { BitsPerSample: 24 } => ((data[offset] | data[offset + 1] << 8 | (sbyte)data[offset + 2] << 16) / 8388608f),
        _ => BitConverter.ToInt32(data.Slice(offset, 4)) / 2147483648f,
    };

    /// <summary>Appends the converted samples of [frames] input frames in [data] to [output].</summary>
    public void Convert(ReadOnlySpan<byte> data, int frames, List<short> output)
    {
        if (frames <= 0) return;
        var bytes = format.BitsPerSample / 8;
        var mono = new float[frames];
        for (var frame = 0; frame < frames; frame++)
        {
            var sum = 0f;
            for (var channel = 0; channel < format.Channels; channel++) sum += Sample(data, frame * format.BlockAlign + channel * bytes);
            mono[frame] = sum / format.Channels;
        }
        if (!started) { previous = mono[0]; started = true; }
        // Positions count input samples: -1 is the previous chunk's last sample, 0..frames-1 this chunk.
        while (position <= frames - 1)
        {
            var index = (int)Math.Floor(position);
            var fraction = (float)(position - index);
            var left = index < 0 ? previous : mono[index];
            var right = index + 1 < frames ? mono[index + 1] : left;
            output.Add(ToPcm(left + (right - left) * fraction));
            position += step;
        }
        position -= frames;
        previous = mono[frames - 1];
    }

    /// <summary>Silence of [samples] output samples (no audio playing: the speech endpointer still hears time pass).</summary>
    public static void Silence(int samples, List<short> output)
    {
        for (var i = 0; i < samples; i++) output.Add(0);
    }

    // Scaled by 32768, as 16-bit input is read, so 16-bit audio passes through unchanged.
    static short ToPcm(float value) => (short)Math.Clamp(Math.Round(value * 32768.0), -32768, 32767);
}
