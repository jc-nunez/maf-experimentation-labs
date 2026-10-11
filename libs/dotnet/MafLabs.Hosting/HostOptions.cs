namespace MafLabs.Hosting;

/// <summary>The host argument contract shared with the Python host (see docs/host-protocol.md).</summary>
public sealed record HostOptions
{
    public string? Target { get; init; }
    public string? Prompt { get; init; }
    public string Output { get; init; } = "text";
    public string? Provider { get; init; }
    public string? Model { get; init; }
    public string? Effort { get; init; }
    public bool Stdio { get; init; }
    public bool List { get; init; }
    public bool Quiet { get; init; }
    public bool AllowAllTools { get; init; }

    public static HostOptions Parse(string[] args)
    {
        var o = new HostOptions();
        for (var i = 0; i < args.Length; i++)
        {
            var a = args[i];
            string Next() => i + 1 < args.Length ? args[++i] : throw new ArgumentException($"{a} needs a value");
            o = a switch
            {
                "-p" or "--prompt" => o with { Prompt = Next() },
                "--output" or "-o" => o with { Output = Next() },
                "--provider" => o with { Provider = Next() },
                "--model" => o with { Model = Next() },
                "--effort" => o with { Effort = Next() },
                "--stdio" => o with { Stdio = true },
                "--list" => o with { List = true },
                "--quiet" => o with { Quiet = true },
                "-y" or "--allow-all-tools" => o with { AllowAllTools = true },
                "--no-trace" => o, // traces are recorded by mafx for .NET hosts
                _ when a.StartsWith('-') => throw new ArgumentException($"unknown option {a}"),
                _ => o with { Target = a },
            };
        }
        return o;
    }
}
