namespace MafLabs.Hosting;

/// <summary>Loads .env files: workspace root (found via maf-labs.yaml) first, then the current directory.</summary>
internal static class Env
{
    public static string? WorkspaceRoot { get; private set; }

    public static void Load()
    {
        var dir = new DirectoryInfo(Directory.GetCurrentDirectory());
        var project = dir.FullName;
        if (Environment.GetEnvironmentVariable("MAFX_HOME") is { Length: > 0 } home)
        {
            dir = new DirectoryInfo(home);
        }
        for (var d = dir; d is not null; d = d.Parent)
        {
            if (File.Exists(Path.Combine(d.FullName, "maf-labs.yaml")))
            {
                WorkspaceRoot = d.FullName;
                LoadFile(Path.Combine(d.FullName, ".env"), overwrite: false);
                break;
            }
        }
        if (project != WorkspaceRoot)
        {
            LoadFile(Path.Combine(project, ".env"), overwrite: true);
        }
    }

    public static string? Get(string name, string? fallback = null)
    {
        var v = Environment.GetEnvironmentVariable(name);
        return string.IsNullOrWhiteSpace(v) || v.StartsWith('<') ? fallback : v;
    }

    public static string Require(string name, string provider) =>
        Get(name) ?? throw new InvalidOperationException($"provider '{provider}' needs {name} (set it in .env)");

    /// <summary>defaults.provider from maf-labs.yaml (tiny line-based read; no YAML dependency).</summary>
    public static string? DefaultProvider()
    {
        if (WorkspaceRoot is null) return null;
        var inDefaults = false;
        foreach (var raw in File.ReadLines(Path.Combine(WorkspaceRoot, "maf-labs.yaml")))
        {
            var line = raw.Split('#')[0];
            if (line.Length > 0 && !char.IsWhiteSpace(line[0])) inDefaults = line.StartsWith("defaults:");
            else if (inDefaults && line.Trim().StartsWith("provider:")) return line.Split(':', 2)[1].Trim();
        }
        return null;
    }

    private static void LoadFile(string path, bool overwrite)
    {
        if (!File.Exists(path)) return;
        foreach (var raw in File.ReadAllLines(path))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#') || !line.Contains('=')) continue;
            var (key, value) = (line[..line.IndexOf('=')].Trim(), line[(line.IndexOf('=') + 1)..].Trim().Trim('"', '\''));
            if (overwrite || Environment.GetEnvironmentVariable(key) is null)
            {
                Environment.SetEnvironmentVariable(key, value);
            }
        }
    }
}
