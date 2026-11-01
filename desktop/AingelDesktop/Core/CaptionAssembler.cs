using System.Collections.Generic;

namespace Aingel.Desktop.Core;

/// <summary>
/// Turns transcription events into lines. Partials are cumulative (each repeats the whole sentence so far); the end
/// of a turn may come as a final transcript, as «speechComplete», or as a final event with no text — seen live with
/// Meta Voice Transcribe — so the line is the final text, or else the turn's last partial, and is emitted once.
/// </summary>
public sealed class CaptionAssembler
{
    readonly Dictionary<string, string> partials = new();
    readonly Dictionary<string, string> speakers = new();

    /// <summary>(the sentence being heard, or null) and (a finished line, or null) after [caption].</summary>
    public (string? Partial, string? Final) Feed(CaptionEvent caption)
    {
        var turn = caption.TurnId ?? "";
        if (caption.Kind == "speaker")
        {
            if (caption.Speaker != null) speakers[turn] = caption.Speaker;
            return (null, null);
        }
        if (caption.Kind == "transcript" && !caption.Final)
        {
            partials[turn] = caption.Text;
            return (caption.Text, null);
        }
        if (caption.Kind is not ("transcript" or "speechComplete")) return (null, null);
        var text = string.IsNullOrWhiteSpace(caption.Text) ? partials.GetValueOrDefault(turn) : caption.Text;
        partials.Remove(turn);
        return (null, string.IsNullOrWhiteSpace(text) ? null : text.Trim());
    }

    /// <summary>The speaker Meta reported for [turn], or null: AINGEL never guesses who spoke.</summary>
    public string? Speaker(string? turn) => speakers.GetValueOrDefault(turn ?? "");
}
