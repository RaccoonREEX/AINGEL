using System.Globalization;
using System.Linq;
using System.Text.Json;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;
using Aingel.Desktop.Core;

namespace Aingel.Desktop;

/// <summary>Sign-in with the AINGEL account (password, then the second factor when enabled), then the profile.</summary>
public partial class LoginWindow : Window
{
    readonly App app;
    // Before a profile is chosen, the language of Windows.
    readonly string locale = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "es" ? "es-EC" : "en-US";
    bool done;

    public LoginWindow(App app)
    {
        this.app = app;
        InitializeComponent();
        string T(string key) => Texts.Get(locale, key);
        Title = Heading.Text = T("login_title");
        UserLabel.Content = "_" + T("username");
        PasswordLabel.Content = "_" + T("password");
        ServerExpander.Header = ServerLabel.Content = T("server");
        Server.Text = app.Settings.Backend;
        SignIn.Content = T("sign_in");
        MfaLabel.Content = "_" + T("mfa_code");
        Verify.Content = T("verify");
        ProfileLabel.Content = "_" + T("profile");
        Continue.Content = T("continue");
        AutomationProperties.SetName(Status, "");
        // Labels do not name their controls for UI Automation in WPF: each input gets its name here (NVDA reads it).
        AutomationProperties.SetName(User, T("username"));
        AutomationProperties.SetName(Password, T("password"));
        AutomationProperties.SetName(Server, T("server"));
        AutomationProperties.SetName(Mfa, T("mfa_code"));
        AutomationProperties.SetName(Profiles, T("profile"));
        Loaded += (_, _) => User.Focus();
        Closed += (_, _) => { if (!done) app.Shutdown(); };
    }

    void Say(string text)
    {
        Status.Text = text;
        AutomationProperties.SetName(Status, text);
        UIElementAutomationPeer.FromElement(Status)?.RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
    }

    void Busy(bool busy) => SignIn.IsEnabled = Verify.IsEnabled = Continue.IsEnabled = !busy;

    async void OnSignIn(object sender, RoutedEventArgs e)
    {
        var backend = Backend.Validate(Server.Text);
        if (backend == null) { ServerExpander.IsExpanded = true; Server.Focus(); Say(Texts.Error(locale, "backend_invalid")); return; }
        Busy(true); Say(Texts.Get(locale, "signing_in"));
        try
        {
            app.Connect(backend);
            var session = await app.Api!.Login(User.Text.Trim(), Password.Password);
            Password.Clear();
            if (session.TryGetProperty("mfa_required", out var mfa) && mfa.ValueKind == JsonValueKind.True)
            {
                Credentials.Visibility = Visibility.Collapsed; MfaPanel.Visibility = Visibility.Visible;
                Say(Texts.Get(locale, "mfa_needed")); Mfa.Focus();
            }
            else await ChooseProfile();
        }
        catch (ApiFailure failure) { Say(Texts.Error(locale, failure.Code)); }
        finally { Busy(false); }
    }

    async void OnVerify(object sender, RoutedEventArgs e)
    {
        Busy(true);
        try { await app.Api!.VerifyMfa(Mfa.Text.Trim()); Mfa.Clear(); await ChooseProfile(); }
        catch (ApiFailure failure) { Say(Texts.Error(locale, failure.Code)); }
        finally { Busy(false); }
    }

    async System.Threading.Tasks.Task ChooseProfile()
    {
        var profiles = await app.Api!.Profiles();
        if (profiles.Count == 0) { Say(Texts.Get(locale, "no_profiles")); return; }
        if (profiles.Count == 1) { Open(profiles[0]); return; }
        Credentials.Visibility = MfaPanel.Visibility = Visibility.Collapsed;
        ProfilePanel.Visibility = Visibility.Visible;
        Profiles.ItemsSource = profiles;
        Profiles.SelectedItem = profiles.FirstOrDefault(p => p.Id == app.Settings.ProfileId) ?? profiles[0];
        Say(Texts.Get(locale, "pick_profile")); Profiles.Focus();
    }

    void OnContinue(object sender, RoutedEventArgs e)
    {
        if (Profiles.SelectedItem is Profile profile) Open(profile);
    }

    void Open(Profile profile)
    {
        done = true;
        app.ShowMain(profile);
        Close();
    }
}
