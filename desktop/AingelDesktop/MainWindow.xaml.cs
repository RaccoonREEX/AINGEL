using System;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Animation;
using Aingel.Desktop.Core;

namespace Aingel.Desktop;

/// <summary>
/// AINGEL's floating window: the Thinking Orb, the actions (also as global shortcuts) and the answer. Captures are
/// one-off and only on request; this window is excluded from them.
/// </summary>
public partial class MainWindow : Window
{
    enum OrbState { Idle, Capturing, Thinking, Error }

    readonly App app;
    readonly Profile profile;
    readonly Speech speech;
    readonly ForegroundTracker tracker = new();
    Hotkeys? hotkeys;
    (string Token, DateTime Until)? session;
    Shot? pending;  // captured with Ctrl+Alt+Q, waiting for the typed question
    bool busy, privateTest, synthetic;
    readonly TextBlock announcer = new() { Height = 1, Opacity = 0, IsHitTestVisible = false };

    string Locale => profile.Locale;
    string T(string key, params object[] args) => Texts.Get(Locale, key, args);

    public MainWindow(App app, Profile profile)
    {
        this.app = app;
        this.profile = profile;
        InitializeComponent();
        speech = new Speech(profile.Locale);
        Title = $"AINGEL · {profile.DisplayName}";
        Topmost = app.Settings.Topmost;
        DescribeWindowButton.Content = $"{T("describe_window")}  ({Hotkeys.Label(Command.DescribeWindow)})";
        DescribeScreenButton.Content = $"{T("describe_screen")}  ({Hotkeys.Label(Command.DescribeScreen)})";
        MoreDetailButton.Content = $"{T("more_detail")}  ({Hotkeys.Label(Command.MoreDetail)})";
        ReadFocusButton.Content = $"{T("read_focus")}  ({Hotkeys.Label(Command.ReadFocus)})";
        StopButton.Content = $"{T("stop_speech")}  ({Hotkeys.Label(Command.StopSpeech)})";
        OpenDocumentButton.Content = $"{T("open_document")}  ({Hotkeys.Label(Command.OpenDocument)})";
        CaptionsButton.Content = $"{T("open_captions")}  ({Hotkeys.Label(Command.Captions)})";
        LevelLabel.Content = "_" + T("level");
        // Labels do not name their controls for UI Automation in WPF: each input gets its name here (NVDA reads it).
        AutomationProperties.SetName(Level, T("level"));
        AutomationProperties.SetName(Question, T("question"));
        AutomationProperties.SetName(Answer, T("answer"));
        Level.ItemsSource = new[] { "level_auto", "level_brief", "level_standard", "level_detailed", "level_deep" }.Select(key => T(key)).ToList();
        Level.SelectedIndex = 0;
        QuestionLabel.Content = $"_{T("question")} ({Hotkeys.Label(Command.AskAboutWindow)})";
        AskButton.Content = T("ask");
        AnswerLabel.Content = "_" + T("answer");
        VoiceBox.Content = T("voice");
        var reader = Speech.ScreenReaderRunning();
        VoiceBox.IsChecked = speech.Available && (app.Settings.Voice ?? !reader);
        VoiceBox.IsEnabled = speech.Available;
        if (reader && VoiceBox.IsChecked != true) { VoiceNote.Text = T("voice_reader"); VoiceNote.Visibility = Visibility.Visible; }
        TopmostBox.Content = T("topmost");
        TopmostBox.IsChecked = Topmost;
        PrivateBox.Content = T("private_test");
        PrivateBox.IsEnabled = VisionFields.PrivateTestAllowed(profile);
        SyntheticBox.Content = T("synthetic");
        PrivacyNote.Text = T("privacy_note");
        ShortcutsNote.Text = T("shortcuts");
        Account.Text = $"{profile.DisplayName} · {app.Api!.Base.Host}";
        SignOutButton.Content = T("sign_out");
        ((StackPanel)((ScrollViewer)Content).Content).Children.Add(announcer);
        AutomationProperties.SetLiveSetting(announcer, AutomationLiveSetting.Polite);
        SetState(OrbState.Idle, T("idle"));
        SourceInitialized += OnSourceInitialized;
        Loaded += async (_, _) => await CheckForUpdate();
        Closed += OnClosed;
    }

    void OnSourceInitialized(object? sender, EventArgs e)
    {
        var source = (HwndSource)PresentationSource.FromVisual(this)!;
        // AINGEL's own window never appears in what it captures.
        ScreenCapture.ExcludeFromCapture(source.Handle);
        hotkeys = new Hotkeys(source, OnCommand);
        if (hotkeys.Failed.Count > 0)
            ShortcutsNote.Text += "\n" + T("hotkeys_failed", string.Join(", ", hotkeys.Failed.Select(Hotkeys.Label)));
    }

    async void OnClosed(object? sender, EventArgs e)
    {
        hotkeys?.Dispose();
        tracker.Dispose();
        speech.Dispose();
        app.Settings.Voice = VoiceBox.IsChecked == true;
        app.Settings.Topmost = Topmost;
        app.Store.SaveSettings(app.Settings);
        if (session is { } open) await app.Api!.CloseVision(open.Token);
        if (!signingOut) app.Shutdown();
    }

    /// <summary>Says when the server's download page has a newer version; installing it stays the person's choice.</summary>
    async Task CheckForUpdate()
    {
        var current = System.Reflection.Assembly.GetExecutingAssembly().GetName().Version?.ToString(3) ?? "0.0.0";
        var latest = await app.Api!.LatestRelease();
        if (ApiClient.Newer(latest, current)) ShortcutsNote.Text = T("update_available", latest!, app.Api.Base.GetLeftPart(UriPartial.Authority)) + "\n\n" + ShortcutsNote.Text;
    }

    void OnCommand(Command command)
    {
        switch (command)
        {
            case Command.DescribeWindow: _ = Describe(wholeScreen: false); break;
            case Command.DescribeScreen: _ = Describe(wholeScreen: true); break;
            case Command.ReadFocus: _ = ReadFocus(); break;
            case Command.AskAboutWindow: CaptureForQuestion(); break;
            case Command.MoreDetail: _ = MoreDetail(); break;
            case Command.StopSpeech: speech.Stop(); break;
            case Command.ShowHide: ShowHide(); break;
            case Command.OpenDocument: ShowWindow(); _ = OpenDocument(); break;
            case Command.Captions: OpenCaptions(); break;
        }
    }

    // --- Orb and announcements -------------------------------------------------------------------------------------

    void SetState(OrbState state, string status)
    {
        Status.Text = status;
        OrbLight.Color = state switch
        {
            OrbState.Capturing => Color.FromRgb(0xF2, 0xA9, 0x00),
            OrbState.Error => Color.FromRgb(0xC0, 0x4B, 0x3A),
            _ => Color.FromRgb(0x5B, 0x8D, 0xEF),
        };
        // A gentle pulse while thinking, unless Windows asks for less motion.
        if (state == OrbState.Thinking && SystemParameters.ClientAreaAnimation)
        {
            var pulse = new DoubleAnimation(1, 1.08, TimeSpan.FromMilliseconds(700)) { AutoReverse = true, RepeatBehavior = RepeatBehavior.Forever };
            OrbScale.BeginAnimation(ScaleTransform.ScaleXProperty, pulse);
            OrbScale.BeginAnimation(ScaleTransform.ScaleYProperty, pulse);
        }
        else
        {
            OrbScale.BeginAnimation(ScaleTransform.ScaleXProperty, null);
            OrbScale.BeginAnimation(ScaleTransform.ScaleYProperty, null);
        }
        UIElementAutomationPeer.FromElement(Status)?.RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
    }

    /// <summary>Shows [text] as the answer; it is spoken by AINGEL's voice, or announced to the screen reader when the
    /// voice is off, never both.</summary>
    void Present(string text)
    {
        Answer.Text = text;
        if (VoiceBox.IsChecked == true) { speech.Speak(text); return; }
        announcer.Text = text;
        AutomationProperties.SetName(announcer, text);
        (UIElementAutomationPeer.FromElement(announcer) ?? UIElementAutomationPeer.CreatePeerForElement(announcer))
            .RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
    }

    void Fail(string code)
    {
        if (VisionFields.EndsSession(code)) session = null;
        var message = code == "synthetic_fixture_only" ? T("synthetic_note") : Texts.Error(Locale, code);
        SetState(OrbState.Error, message);
        Present(message);
        if (code == "authentication_required") _ = SignOut();
    }

    string? SelectedLevel() => Level.SelectedIndex > 0 ? VisionFields.Levels[Level.SelectedIndex - 1] : null;

    bool SessionLive => session is { } open && DateTime.UtcNow < open.Until;

    // --- Actions --------------------------------------------------------------------------------------------------

    /// <summary>Captures the active window (or its whole monitor) now and describes it.</summary>
    async Task Describe(bool wholeScreen, string? question = null)
    {
        if (busy) return;
        Shot? shot = null;
        if (!synthetic)
        {
            var target = tracker.Target();
            if (target == IntPtr.Zero) { Fail("window_not_visible"); return; }
            SetState(OrbState.Capturing, T("capturing", ScreenCapture.Title(target)));
            try { ScreenCapture.ExcludeOwnWindows(); shot = wholeScreen ? ScreenCapture.Monitor(target) : ScreenCapture.Window(target); }
            catch (ApiFailure failure) { Fail(failure.Code); return; }
            catch (Exception e) when (e is ExternalException or ArgumentException or InvalidOperationException) { Fail("capture_failed"); return; }
        }
        await Send(shot, question);
    }

    /// <summary>A new picture ([shot], or the server's synthetic screen) with an optional question.</summary>
    async Task Send(Shot? shot, string? question)
    {
        var level = SelectedLevel();
        try
        {
            var fields = synthetic ? VisionFields.Fixture(Locale, level) : VisionFields.Screen(profile, privateTest, question, level);
            if (synthetic && !string.IsNullOrWhiteSpace(question)) { Fail("synthetic_fixture_only"); return; }
            await Run(shot?.Jpeg, fields, deep: level == "deep" || Deep(question), opensSession: true);
        }
        catch (ApiFailure failure) { Fail(failure.Code); }
    }

    static bool Deep(string? question) =>
        question != null && (question.Contains("a detalle", StringComparison.OrdinalIgnoreCase) || question.Contains("a fondo", StringComparison.OrdinalIgnoreCase)
                             || question.Contains("in depth", StringComparison.OrdinalIgnoreCase));

    async Task Run(byte[]? jpeg, System.Collections.Generic.Dictionary<string, string> fields, bool deep, bool opensSession)
    {
        if (opensSession && session is { } previous) { session = null; _ = app.Api!.CloseVision(previous.Token); }
        busy = true;
        SetState(OrbState.Thinking, T(deep ? "thinking_deep" : "thinking"));
        try
        {
            var result = await app.Api!.Vision(jpeg, fields);
            var text = result.GetProperty("text").GetString() ?? "";
            if (result.TryGetProperty("mode", out var mode) && mode.GetString() == "mock") text = T("mock_note") + " " + text;
            if (result.TryGetProperty("session", out var token) && token.ValueKind == JsonValueKind.String
                && result.TryGetProperty("session_seconds", out var seconds) && seconds.TryGetInt32(out var value) && value > 0)
                session = (token.GetString()!, DateTime.UtcNow.AddSeconds(value - 5));
            SetState(OrbState.Idle, T("idle"));
            Present(text);
        }
        catch (ApiFailure failure) { Fail(failure.Code); }
        finally { busy = false; }
    }

    /// <summary>Ctrl+Alt+Q: the window is captured at once, as it is, then AINGEL waits for the typed question.</summary>
    void CaptureForQuestion()
    {
        if (busy) return;
        if (!synthetic)
        {
            var target = tracker.Target();
            try { ScreenCapture.ExcludeOwnWindows(); pending = ScreenCapture.Window(target); }
            catch (ApiFailure failure) { Fail(failure.Code); return; }
            catch (Exception e) when (e is ExternalException or ArgumentException or InvalidOperationException) { Fail("capture_failed"); return; }
        }
        ShowWindow();
        Question.Focus();
        SetState(OrbState.Capturing, T("captured_ask", pending?.Title ?? T("synthetic")));
    }

    async void OnAsk(object sender, RoutedEventArgs e) => await Ask();

    async Task Ask()
    {
        var question = Question.Text.Trim();
        if (question.Length == 0 || busy) return;
        if (pending != null || (synthetic && !SessionLive))
        {
            var shot = pending; pending = null;
            await Send(shot, question);
        }
        else if (SessionLive)
        {
            if (synthetic) { Fail("synthetic_fixture_only"); return; }
            await Run(null, VisionFields.FollowUp(Locale, session!.Value.Token, question, SelectedLevel()), Deep(question), opensSession: false);
        }
        else await Describe(wholeScreen: false, question);
        Question.Clear();
    }

    void OnQuestionKey(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter) { e.Handled = true; _ = Ask(); }
        else if (e.Key == Key.Escape && pending != null) { e.Handled = true; pending = null; SetState(OrbState.Idle, T("capture_cancelled")); }
    }

    /// <summary>The same picture again, explored in depth (three analysis steps on the server).</summary>
    async Task MoreDetail()
    {
        if (busy) return;
        if (!SessionLive) { SetState(OrbState.Idle, T("no_session")); Present(T("no_session")); return; }
        await Run(null, VisionFields.FollowUp(Locale, session!.Value.Token, null, "deep"), deep: true, opensSession: false);
    }

    /// <summary>The focused control, read locally (UI Automation): nothing is captured or sent.</summary>
    async Task ReadFocus()
    {
        var text = await Task.Run(() => FocusReader.Describe(Locale));
        Present(text);
    }

    void ShowHide()
    {
        if (IsVisible && WindowState != WindowState.Minimized && IsActive) WindowState = WindowState.Minimized;
        else ShowWindow();
    }

    void ShowWindow()
    {
        Show();
        if (WindowState == WindowState.Minimized) WindowState = WindowState.Normal;
        Activate();
    }

    // --- Buttons and options --------------------------------------------------------------------------------------

    async void OnOpenDocument(object sender, RoutedEventArgs e) => await OpenDocument();

    CaptionsWindow? captions;

    void OnCaptions(object sender, RoutedEventArgs e) => OpenCaptions();

    /// <summary>One captions window; it captures nothing until the person starts it there.</summary>
    void OpenCaptions()
    {
        if (captions == null)
        {
            captions = new CaptionsWindow(app, profile) { Owner = this };
            captions.Closed += (_, _) => captions = null;
        }
        captions.Show();
        captions.Activate();
    }

    /// <summary>A PDF or a page photo chosen by the person (or, in the synthetic test, a server document).</summary>
    async Task OpenDocument()
    {
        if (busy) return;
        string? fixture = null;
        byte[]? file = null;
        var name = "";
        if (synthetic)
        {
            var choice = MessageBox.Show(this, T("doc_pick_fixture"), T("open_document"), MessageBoxButton.YesNoCancel, MessageBoxImage.Question);
            if (choice == MessageBoxResult.Cancel) return;
            fixture = choice == MessageBoxResult.Yes ? "book_pdf" : "scanned_pdf";
        }
        else
        {
            var dialog = new Microsoft.Win32.OpenFileDialog { Title = T("open_document"), Filter = T("doc_filter") };
            if (dialog.ShowDialog(this) != true) return;
            try { file = await System.IO.File.ReadAllBytesAsync(dialog.FileName); }
            catch (System.IO.IOException) { Fail("document_invalid"); return; }
            name = System.IO.Path.GetFileName(dialog.FileName);
        }
        busy = true;
        SetState(OrbState.Thinking, T("thinking"));
        try
        {
            var opened = await app.Api!.OpenDocument(file, name, DocumentWindow.OpenFields(profile, privateTest, fixture));
            SetState(OrbState.Idle, T("idle"));
            new DocumentWindow(app, profile, VoiceBox.IsChecked == true ? speech : Speech.Silent, opened) { Owner = this }.Show();
        }
        catch (ApiFailure failure) { Fail(failure.Code); }
        finally { busy = false; }
    }

    async void OnDescribeWindow(object sender, RoutedEventArgs e) => await Describe(wholeScreen: false);
    async void OnDescribeScreen(object sender, RoutedEventArgs e) => await Describe(wholeScreen: true);
    async void OnMoreDetail(object sender, RoutedEventArgs e) => await MoreDetail();
    async void OnReadFocus(object sender, RoutedEventArgs e) => await ReadFocus();
    void OnStop(object sender, RoutedEventArgs e) => speech.Stop();
    void OnVoice(object sender, RoutedEventArgs e) { if (VoiceBox.IsChecked != true) speech.Stop(); VoiceNote.Visibility = Visibility.Collapsed; }
    void OnTopmost(object sender, RoutedEventArgs e) => Topmost = TopmostBox.IsChecked == true;

    void OnPrivate(object sender, RoutedEventArgs e)
    {
        if (PrivateBox.IsChecked == true && !privateTest)
        {
            var answer = MessageBox.Show(this, T("private_confirm"), T("private_test"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No);
            PrivateBox.IsChecked = answer == MessageBoxResult.Yes;
        }
        privateTest = PrivateBox.IsChecked == true;
    }

    void OnSynthetic(object sender, RoutedEventArgs e)
    {
        synthetic = SyntheticBox.IsChecked == true;
        pending = null;
        if (session is { } open) { session = null; _ = app.Api!.CloseVision(open.Token); }
        ModeNote.Text = T("synthetic_note");
        ModeNote.Visibility = synthetic ? Visibility.Visible : Visibility.Collapsed;
    }

    bool signingOut;

    async void OnSignOut(object sender, RoutedEventArgs e) => await SignOut();

    async Task SignOut()
    {
        if (signingOut) return;
        signingOut = true;
        if (session is { } open) { session = null; await app.Api!.CloseVision(open.Token); }
        await app.SignOut();
        Close();
    }
}
