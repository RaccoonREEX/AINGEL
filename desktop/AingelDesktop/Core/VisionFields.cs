using System.Collections.Generic;

namespace Aingel.Desktop.Core;

/// <summary>
/// Request fields for deep vision (backend assistance.vision), as on Android (Vision.kt). The server reads the level
/// and the kind of image from the question unless named; each answer opens a short follow-up session.
/// </summary>
public static class VisionFields
{
    public static readonly string[] Levels = { "brief", "standard", "detailed", "deep" };
    public const string ScreenFixture = "screen_desktop";

    /// <summary>The private test of one's own material: only the owner who is the person (care.consent).</summary>
    public static bool PrivateTestAllowed(Profile profile) => profile.Role == "owner" && profile.SubjectStatus == "self";

    /// <summary>A capture of this computer's screen, under the person's own authorization (checked by the server).</summary>
    public static Dictionary<string, string> Screen(Profile profile, bool privateTest, string? question, string? level)
    {
        var fields = new Dictionary<string, string> { ["locale"] = profile.Locale, ["profile"] = profile.Id, ["source_kind"] = "screen" };
        if (privateTest)
        {
            if (!PrivateTestAllowed(profile)) throw new ApiFailure("private_test_consent_required");
            fields["private_test"] = "true";
        }
        Add(fields, question, level);
        return fields;
    }

    /// <summary>The server's synthetic Windows screen: its id and the level only. Typed text is free content and never
    /// goes with a fixture (the server refuses it).</summary>
    public static Dictionary<string, string> Fixture(string locale, string? level)
    {
        var fields = new Dictionary<string, string> { ["locale"] = locale, ["fixture"] = ScreenFixture, ["source_kind"] = "screen" };
        Add(fields, null, level);
        return fields;
    }

    /// <summary>A follow-up about the session's picture: no profile or declaration (the server rechecks consent).</summary>
    public static Dictionary<string, string> FollowUp(string locale, string session, string? question, string? level)
    {
        var fields = new Dictionary<string, string> { ["locale"] = locale, ["session"] = session };
        Add(fields, question, level);
        return fields;
    }

    static void Add(Dictionary<string, string> fields, string? question, string? level)
    {
        var text = question?.Trim();
        if (!string.IsNullOrEmpty(text)) fields["question"] = text.Length > 600 ? text[..600] : text;
        if (level != null && System.Array.IndexOf(Levels, level) >= 0) fields["detail_level"] = level;
    }

    /// <summary>Errors after which the session's picture is gone: expired, or the person's decisions changed.</summary>
    public static bool EndsSession(string code) =>
        code is "visual_session_expired" or "consent_changed" or "camera_consent_revoked" or "privacy_review_required";
}
