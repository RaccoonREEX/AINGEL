using System;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using Aingel.Desktop.Core;

namespace Aingel.Desktop;

public partial class App : Application
{
    internal SessionStore Store { get; } = new();
    internal Settings Settings { get; private set; } = new();
    internal ApiClient? Api { get; private set; }

    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        Settings = Store.LoadSettings();
        // A session saved earlier opens AINGEL directly; otherwise, or when it ended, the sign-in window.
        var profile = await Restore();
        if (profile != null) ShowMain(profile); else ShowLogin();
    }

    async Task<Profile?> Restore()
    {
        var backend = Backend.Validate(Settings.Backend);
        if (backend == null || Settings.ProfileId == null) return null;
        try
        {
            Connect(backend, restore: true);
            var session = await Api!.SessionState();
            if (session.GetProperty("user").ValueKind == System.Text.Json.JsonValueKind.Null) return null;
            return (await Api.Profiles()).FirstOrDefault(p => p.Id == Settings.ProfileId);
        }
        catch (ApiFailure) { return null; }
    }

    internal void Connect(string backend, bool restore = false)
    {
        Api?.Dispose();
        var uri = new Uri(backend);
        Api = new ApiClient(backend, restore ? Store.LoadCookies(uri) : null);
        Settings.Backend = backend;
    }

    internal void ShowLogin()
    {
        var login = new LoginWindow(this);
        login.Show();
    }

    internal void ShowMain(Profile profile)
    {
        Settings.ProfileId = profile.Id;
        Store.SaveSettings(Settings);
        Store.SaveCookies(Api!.Cookies, Api.Base);
        new MainWindow(this, profile).Show();
    }

    internal async Task SignOut()
    {
        if (Api != null)
        {
            try { await Api.Logout(); } catch (ApiFailure) { }
        }
        Store.ClearCookies();
        Settings.ProfileId = null;
        Store.SaveSettings(Settings);
        ShowLogin();
    }
}
