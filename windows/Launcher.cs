using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Globalization;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: AssemblyTitle("Манга-студия")]
[assembly: AssemblyDescription("Локальная раскраска манги")]
[assembly: AssemblyVersion("2.2.0.0")]
[assembly: AssemblyFileVersion("2.2.0.0")]

internal static class Launcher
{
    [STAThread]
    private static void Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string app = Path.Combine(root, "app.py");
        try
        {
            string pointer = Path.Combine(root, ".runtime-path");
            string runtime = File.Exists(pointer) ? Path.GetFullPath(Path.Combine(root, File.ReadAllText(pointer).Trim())) : root;
            string python = Path.Combine(runtime, @".venv\Scripts\pythonw.exe");
            if (!File.Exists(python) || !File.Exists(app))
                throw new FileNotFoundException(SetupMessage(root));
            var start = new ProcessStartInfo(python, "\"" + app + "\"")
            {
                WorkingDirectory = root, UseShellExecute = false
            };
            start.EnvironmentVariables["MANGA_STUDIO_HOME"] = runtime;
            Process.Start(start);
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "Manga Studio 2.2", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private static string SetupMessage(string root)
    {
        var culture = CultureInfo.CurrentUICulture;
        string code = culture.TwoLetterISOLanguageName;
        if (code == "pt") code = "pt-BR";
        if (code == "zh") code = culture.Name.IndexOf("TW", StringComparison.OrdinalIgnoreCase) >= 0 ||
            culture.Name.IndexOf("HK", StringComparison.OrdinalIgnoreCase) >= 0 ||
            culture.Name.IndexOf("Hant", StringComparison.OrdinalIgnoreCase) >= 0 ? "zh-Hant" : "zh-Hans";
        string path = Path.Combine(root, "studio", "locales", code + ".json");
        if (File.Exists(path))
        {
            var catalog = new JavaScriptSerializer().Deserialize<Dictionary<string,string>>(File.ReadAllText(path));
            return catalog["Не найдено окружение приложения. Выполните setup.ps1, как описано в README.md."];
        }
        return "Run setup.ps1 as described in README.md.";
    }
}
