using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;

namespace Aingel.Setup;

/// <summary>
/// The guided installer: what it installs and where, the requirements, the installation, and the end. Every step is
/// shown, never silent; uninstalling asks first and keeps the person's preferences unless they choose otherwise.
/// </summary>
public partial class SetupWindow : Window
{
    enum Step { Welcome, Blocked, Working, Done, Failed, UninstallAsk, Uninstalled }

    readonly Places places;
    readonly Installer installer;
    readonly bool es = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "es";
    Step step;

    string L(string spanish, string english) => es ? spanish : english;

    public SetupWindow(Places places, bool uninstall)
    {
        this.places = places;
        installer = new Installer(places);
        InitializeComponent();
        Title = uninstall ? L("Desinstalar AINGEL Desktop", "Uninstall AINGEL Desktop") : L("Instalar AINGEL Desktop", "Install AINGEL Desktop");
        DesktopBox.Content = L("Crear también un acceso directo en el escritorio", "Also create a desktop shortcut");
        LaunchBox.Content = L("Abrir AINGEL Desktop al cerrar", "Open AINGEL Desktop when closing");
        PreferencesBox.Content = L("Borrar también mis preferencias y la sesión guardada", "Also delete my preferences and saved session");
        Go(uninstall ? Step.UninstallAsk : Step.Welcome);
    }

    void Go(Step next, string? detail = null)
    {
        step = next;
        var installed = installer.InstalledVersion();
        var version = Installer.Version;
        (string heading, string body) = next switch
        {
            Step.Welcome => (installed == null ? L($"Instalar AINGEL Desktop {version}", $"Install AINGEL Desktop {version}") : L($"Actualizar AINGEL Desktop {installed} a {version}", $"Update AINGEL Desktop {installed} to {version}"),
                L($"AINGEL Desktop describe tu pantalla, lee documentos y subtitula el audio del equipo, con tu cuenta de AINGEL.\n\nSe instala solo para tu usuario de Windows, en {places.InstallDir}, sin permisos de administrador. Añade una entrada en el menú Inicio y aparece en Configuración > Aplicaciones para desinstalarlo. No instala servicios ni se inicia solo: captura la pantalla o el audio únicamente cuando tú lo pides.\n\nEditor: {Installer.Publisher}. Este instalador no está firmado con un certificado de código: Windows puede mostrar un aviso de SmartScreen. Comprueba su SHA-256 en la página de descarga.",
                  $"AINGEL Desktop describes your screen, reads documents and captions the computer's audio, with your AINGEL account.\n\nIt installs for your Windows user only, in {places.InstallDir}, without administrator rights. It adds a Start menu entry and appears in Settings > Apps to uninstall it. It installs no services and does not start on its own: it captures the screen or audio only when you ask.\n\nPublisher: {Installer.Publisher}. This installer is not signed with a code-signing certificate: Windows may show a SmartScreen warning. Check its SHA-256 on the download page.")),
            Step.Blocked => (L("No se puede instalar todavía", "It can't be installed yet"), detail ?? ""),
            Step.Working => (L("Instalando…", "Installing…"), L("Comprobando el paquete y copiando los archivos.", "Checking the package and copying the files.")),
            Step.Done => (L("AINGEL Desktop está instalado", "AINGEL Desktop is installed"),
                L($"Está en el menú Inicio como «AINGEL Desktop». Tus preferencias se conservan entre versiones. Para desinstalarlo: Configuración > Aplicaciones > AINGEL Desktop > Desinstalar.\n\nRegistro de la instalación (sin datos personales): {places.Log}",
                  $"It is in the Start menu as «AINGEL Desktop». Your preferences are kept between versions. To uninstall it: Settings > Apps > AINGEL Desktop > Uninstall.\n\nInstallation log (no personal data): {places.Log}")),
            Step.Failed => (L("La instalación no terminó", "The installation did not finish"), detail ?? ""),
            Step.UninstallAsk => (L("Desinstalar AINGEL Desktop", "Uninstall AINGEL Desktop"),
                L($"Se borrarán el programa ({places.InstallDir}), su entrada del menú Inicio, el acceso directo del escritorio y su registro en Configuración. Tu cuenta de AINGEL no se toca.",
                  $"The program ({places.InstallDir}), its Start menu entry, the desktop shortcut and its Settings entry will be removed. Your AINGEL account is not affected.")),
            Step.Uninstalled => (L("AINGEL Desktop se desinstaló", "AINGEL Desktop was uninstalled"),
                PreferencesBox.IsChecked == true ? L("También se borraron tus preferencias y la sesión guardada.", "Your preferences and saved session were deleted too.")
                                                 : L("Tus preferencias se conservaron por si lo vuelves a instalar.", "Your preferences were kept in case you install it again.")),
            _ => ("", ""),
        };
        Heading.Text = heading;
        Body.Text = body;
        AutomationProperties.SetName(Body, body);
        UIElementAutomationPeer.FromElement(Body)?.RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
        DesktopBox.Visibility = next == Step.Welcome ? Visibility.Visible : Visibility.Collapsed;
        LaunchBox.Visibility = next == Step.Done ? Visibility.Visible : Visibility.Collapsed;
        PreferencesBox.Visibility = next == Step.UninstallAsk ? Visibility.Visible : Visibility.Collapsed;
        Progress.Visibility = next == Step.Working ? Visibility.Visible : Visibility.Collapsed;
        Details.Text = next is Step.Welcome or Step.UninstallAsk ? L($"Versión {version} · {Installer.Publisher}", $"Version {version} · {Installer.Publisher}") : "";
        NextButton.Content = next switch
        {
            Step.Welcome => installer.InstalledVersion() == null ? L("Instalar", "Install") : L("Actualizar", "Update"),
            Step.UninstallAsk => L("Desinstalar", "Uninstall"),
            Step.Blocked => L("Volver a comprobar", "Check again"),
            _ => L("Cerrar", "Close"),
        };
        NextButton.IsEnabled = next != Step.Working;
        BackButton.Content = L("Cancelar", "Cancel");
        BackButton.Visibility = next is Step.Welcome or Step.Blocked or Step.UninstallAsk ? Visibility.Visible : Visibility.Collapsed;
        NextButton.Focus();
    }

    async void OnNext(object sender, RoutedEventArgs e)
    {
        switch (step)
        {
            case Step.Welcome:
            case Step.Blocked:
                var problems = Installer.Requirements(Environment.OSVersion.Version, new DriveInfo(Path.GetPathRoot(places.InstallDir)!).AvailableFreeSpace, installer.AppRunning());
                if (problems.Count > 0) { Go(Step.Blocked, string.Join("\n\n", problems.ConvertAll(Problem))); return; }
                await Install();
                break;
            case Step.UninstallAsk:
                if (installer.AppRunning()) { Go(Step.UninstallAsk); Body.Text = Problem("app_running"); return; }
                try { installer.Uninstall(PreferencesBox.IsChecked == true); Go(Step.Uninstalled); }
                catch (Exception error) when (error is IOException or UnauthorizedAccessException) { Go(Step.Failed, Problem("files_in_use")); }
                break;
            case Step.Done:
                if (LaunchBox.IsChecked == true) Process.Start(new ProcessStartInfo(places.AppExe) { UseShellExecute = true });
                Close();
                break;
            default:
                Close();
                break;
        }
    }

    async Task Install()
    {
        Go(Step.Working);
        var desktop = DesktopBox.IsChecked == true;
        var setup = Environment.ProcessPath!;
        try
        {
            await Task.Run(() => installer.Install(Installer.Payload(), setup, desktop, Installer.Version));
            LaunchBox.IsChecked = true;
            Go(Step.Done);
        }
        catch (SetupFailure failure) { Go(Step.Failed, Problem(failure.Code)); }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException) { Go(Step.Failed, Problem("files_in_use")); }
    }

    string Problem(string code) => code switch
    {
        "windows_too_old" => L("Hace falta Windows 10 versión 2004 o posterior, o Windows 11.", "Windows 10 version 2004 or later, or Windows 11, is required."),
        "disk_space" => L("Hacen falta al menos 50 MB libres en el disco.", "At least 50 MB of free disk space is required."),
        "app_running" => L("AINGEL Desktop está abierto. Ciérralo y vuelve a comprobar.", "AINGEL Desktop is open. Close it and check again."),
        "payload_damaged" or "payload_missing" => L("El instalador está dañado o incompleto: su contenido no coincide con su SHA-256. Descárgalo otra vez desde la página oficial. No se instaló nada.", "The installer is damaged or incomplete: its content does not match its SHA-256. Download it again from the official page. Nothing was installed."),
        "files_in_use" => L("Algún archivo está en uso o no se puede escribir. Cierra AINGEL Desktop e inténtalo de nuevo.", "A file is in use or can't be written. Close AINGEL Desktop and try again."),
        _ => L("No se pudo completar. Inténtalo de nuevo.", "It couldn't be completed. Please try again."),
    };

    void OnCancel(object sender, RoutedEventArgs e) => Close();
}
