using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;

// Stable entry point: only the pointer changes while the installed app is running.
internal static class Launcher
{
    internal static string Quote(string value)
    {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value)
        {
            if (c == '\\') { slashes++; continue; }
            result.Append('\\', c == '"' ? slashes * 2 + 1 : slashes);
            result.Append(c);
            slashes = 0;
        }
        result.Append('\\', slashes * 2);
        return result.Append('"').ToString();
    }

    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string pointer = Path.Combine(root, "active-slot.txt");
            string target;
            if (File.Exists(pointer))
            {
                string slot;
                using (var file = new FileStream(pointer, FileMode.Open, FileAccess.Read,
                                                FileShare.ReadWrite | FileShare.Delete))
                using (var reader = new StreamReader(file)) slot = reader.ReadToEnd().Trim();
                if (!Regex.IsMatch(slot, @"\A[0-9]+(?:\.[0-9]+){0,3}-[0-9]+\z"))
                    throw new IOException("설치 경로 정보가 올바르지 않습니다.");
                target = Path.Combine(root, "versions", slot, "DQAConnect.exe");
                if (File.ReadAllText(Path.Combine(Path.GetDirectoryName(target), "install-complete.txt")).Trim()
                    != slot.Substring(0, slot.LastIndexOf('-'))
                    || !File.Exists(Path.Combine(Path.GetDirectoryName(target), "runtime", "python.exe")))
                    throw new IOException("설치가 완료되지 않았습니다.");
            }
            else
            {
                // A failed first migration can still launch the legacy installation.
                bool stable = String.Equals(Path.GetFileName(Environment.GetCommandLineArgs()[0]),
                                            "DQALauncher.exe", StringComparison.OrdinalIgnoreCase);
                target = Path.Combine(root, "DQAConnect.legacy.exe");
                if (stable && File.Exists(Path.Combine(root, "DQAConnect.exe")))
                    target = Path.Combine(root, "DQAConnect.exe");
            }
            if (!File.Exists(target)) throw new IOException("설치 파일을 찾을 수 없습니다.");
            Process.Start(new ProcessStartInfo(target, String.Join(" ", args.Select(Quote))) {
                UseShellExecute = false, WorkingDirectory = Path.GetDirectoryName(target)
            });
            return 0;
        }
        catch (Exception)
        {
            MessageBox.Show("DQA를 시작하지 못했습니다. 설치 프로그램을 다시 실행해 주세요.",
                            "DQA", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
