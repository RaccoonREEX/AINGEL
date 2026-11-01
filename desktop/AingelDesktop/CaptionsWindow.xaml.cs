using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;
using System.Windows.Controls;
using System.Windows.Threading;
using Aingel.Desktop.Core;

namespace Aingel.Desktop;

/// <summary>
/// Captions of what this computer plays (a meeting, a video): system audio captured with WASAPI loopback only while
/// captions are on, with a red dot and the window title saying so. Every start asks for confirmation, because other
/// people's voices may be heard. Sessions renew on their own before the server's 10-minute limit.
/// </summary>
public partial class CaptionsWindow : Window
{
    static readonly TimeSpan Renewal = TimeSpan.FromMinutes(9.5);
    readonly App app;
    readonly Profile profile;
    readonly TextBlock announcer = new() { Height = 1, Opacity = 0, IsHitTestVisible = false };
    readonly CaptionAssembler assembler = new();
    readonly DispatcherTimer renew;
    LoopbackCapture? capture;
    CaptionsClient? client;
    bool running, privateTest;

    string T(string key, params object[] args) => Texts.Get(profile.Locale, key, args);

    public CaptionsWindow(App app, Profile profile)
    {
        this.app = app;
        this.profile = profile;
        InitializeComponent();
        Title = T("captions_title");
        StartButton.Content = T("captions_start");
        StopButton.Content = T("captions_stop");
        SmallerButton.Content = T("captions_smaller");
        LargerButton.Content = T("captions_larger");
        ClearButton.Content = T("captions_clear");
        AnnounceBox.Content = T("captions_announce");
        AnnounceBox.IsChecked = Speech.ScreenReaderRunning();
        PrivateBox.Content = T("captions_private");
        PrivateBox.IsEnabled = VisionFields.PrivateTestAllowed(profile);
        Note.Text = T("captions_note");
        AutomationProperties.SetName(Transcript, T("captions_transcript"));
        AutomationProperties.SetName(Partial, T("captions_now"));
        // At the top: the DockPanel's last child fills the window, and that is the transcript.
        DockPanel.SetDock(announcer, Dock.Top);
        ((DockPanel)Content).Children.Insert(0, announcer);
        AutomationProperties.SetLiveSetting(announcer, AutomationLiveSetting.Polite);
        Status.Text = T("captions_idle");
        renew = new DispatcherTimer { Interval = Renewal };
        renew.Tick += async (_, _) => await Renew();
        Closed += async (_, _) => await StopAll();
    }

    void Say(string text)
    {
        Status.Text = text;
        UIElementAutomationPeer.FromElement(Status)?.RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
    }

    async void OnStart(object sender, RoutedEventArgs e)
    {
        if (running) return;
        // Every time: the audio may hold other people's voices, and it goes to Meta.
        if (MessageBox.Show(this, T("captions_confirm"), T("captions_title"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes) return;
        StartButton.IsEnabled = false;
        Say(T("captions_connecting"));
        try
        {
            client = await Connect();
            capture = new LoopbackCapture();
            // Frames arrive on the capture thread, in order; a closed connection ends the session (Ended).
            capture.Start(frame => client?.SendAudio(frame).GetAwaiter().GetResult());
            running = true;
            renew.Start();
            LiveDot.Visibility = Visibility.Visible;
            Title = "● " + T("captions_running");
            StopButton.IsEnabled = true;
            Say(T("captions_running"));
        }
        catch (ApiFailure failure)
        {
            await StopAll();
            Say(Error(failure.Code));
        }
        catch (NotSupportedException)
        {
            await StopAll();
            Say(Error("system_audio_unavailable"));
        }
    }

    async Task<CaptionsClient> Connect()
    {
        var next = new CaptionsClient();
        next.Caption += caption => Dispatcher.Invoke(() => Show(caption));
        next.Ended += reason => Dispatcher.Invoke(async () => await Ended(next, reason));
        try { await next.Start(app.Api!, profile, privateTest); }
        catch { await next.DisposeAsync(); throw; }
        return next;
    }

    /// <summary>A new server session a little before the 10-minute limit; the old one finishes its last sentence.</summary>
    async Task Renew()
    {
        if (!running) return;
        try
        {
            var next = await Connect();
            var old = client;
            client = next;
            if (old != null) await old.Stop();
        }
        catch (ApiFailure failure) { await StopAll(); Say(Error(failure.Code)); }
    }

    async Task Ended(CaptionsClient ended, string? reason)
    {
        if (ended != client || !running)
        {
            // A renewed session, or one stopped by the person, finishing its last sentence.
            if (ended == client) client = null;
            await ended.DisposeAsync();
            return;
        }
        await StopAll();
        Say(reason == null ? T("captions_idle") : Error(reason));
    }

    void Show(CaptionEvent caption)
    {
        var (partial, final) = assembler.Feed(caption);
        // A speaker is named only when Meta reported one for this turn: never guessed.
        var label = assembler.Speaker(caption.TurnId);
        var prefix = label != null ? T("captions_speaker", label) + ": " : "";
        if (partial != null) { Partial.Text = prefix + partial; return; }
        if (final == null) return;
        Partial.Text = "";
        var line = $"[{DateTime.Now:HH:mm}] {prefix}{final}";
        Transcript.AppendText((Transcript.Text.Length > 0 ? Environment.NewLine : "") + line);
        Transcript.ScrollToEnd();
        if (AnnounceBox.IsChecked == true)
        {
            announcer.Text = prefix + final;
            AutomationProperties.SetName(announcer, announcer.Text);
            (UIElementAutomationPeer.FromElement(announcer) ?? UIElementAutomationPeer.CreatePeerForElement(announcer))
                .RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
        }
    }

    async void OnStop(object sender, RoutedEventArgs e)
    {
        var finishing = client;
        capture?.Dispose();
        capture = null;
        if (finishing != null) await finishing.Stop();  // its last sentence still arrives, then it closes
        running = false;
        renew.Stop();
        LiveDot.Visibility = Visibility.Collapsed;
        Title = T("captions_title");
        StartButton.IsEnabled = true;
        StopButton.IsEnabled = false;
        Say(T("captions_idle"));
    }

    async Task StopAll()
    {
        running = false;
        renew.Stop();
        capture?.Dispose();
        capture = null;
        var old = client;
        client = null;
        if (old != null) await old.DisposeAsync();
        LiveDot.Visibility = Visibility.Collapsed;
        Title = T("captions_title");
        StartButton.IsEnabled = true;
        StopButton.IsEnabled = false;
    }

    void OnSmaller(object sender, RoutedEventArgs e) { Transcript.FontSize = Math.Max(14, Transcript.FontSize - 2); Partial.FontSize = Math.Max(18, Partial.FontSize - 2); }
    void OnLarger(object sender, RoutedEventArgs e) { Transcript.FontSize = Math.Min(48, Transcript.FontSize + 2); Partial.FontSize = Math.Min(64, Partial.FontSize + 2); }
    void OnClear(object sender, RoutedEventArgs e) { Transcript.Clear(); Partial.Text = ""; }

    /// <summary>Audio wording for the server's codes: captions need the microphone and voice permissions, not images.</summary>
    string Error(string code) => code switch
    {
        "privacy_review_required" => T("captions_privacy"),
        "consent_changed" or "camera_consent_revoked" => T("captions_consent_changed"),
        "caption_session_expired" => T("captions_idle"),
        "system_audio_unavailable" => T("captions_no_audio"),
        "network_failed" or "throttled" or "meta_access_denied" or "adult_declaration_required" or "private_test_consent_required" or "meta_quota_exceeded"
            => Texts.Error(profile.Locale, code),
        _ => T("captions_failed"),
    };

    void OnPrivate(object sender, RoutedEventArgs e)
    {
        if (PrivateBox.IsChecked == true && !privateTest)
        {
            var answer = MessageBox.Show(this, T("captions_private_confirm"), T("captions_private"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No);
            PrivateBox.IsChecked = answer == MessageBoxResult.Yes;
        }
        privateTest = PrivateBox.IsChecked == true;
    }
}
