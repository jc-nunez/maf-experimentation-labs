using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace MafLabs.Hosting;

/// <summary>
/// Shared .NET host. Projects only register agents; the host handles configuration, providers and the
/// run surfaces (-p run-once, interactive, --stdio JSONL for mafx) exactly like the python host.
/// </summary>
/// <example>
/// var host = MafLabsHost.Create(args);
/// host.AddAgent("greeter", instructions: "You are friendly.", tools: [AIFunctionFactory.Create(Weather.Get)]);
/// return await host.RunAsync();
/// </example>
public sealed class MafLabsHost
{
    private readonly Dictionary<string, (string? Description, Func<IChatClient, AIAgent> Factory, string[] Tools)> _agents =
        new(StringComparer.OrdinalIgnoreCase);

    private MafLabsHost(HostOptions options) => Options = options;

    public HostOptions Options { get; }

    public static MafLabsHost Create(string[] args)
    {
        Env.Load();
        return new MafLabsHost(HostOptions.Parse(args));
    }

    /// <summary>Register an agent built from instructions and tools on the host's chat client.</summary>
    public MafLabsHost AddAgent(string name, string instructions, IList<AITool>? tools = null, string? description = null)
    {
        _agents[name] = (description,
            client => client.AsAIAgent(instructions: instructions, name: name, description: description, tools: tools),
            (tools ?? []).Select(t => t.Name).ToArray());
        return this;
    }

    /// <summary>Register an agent with full control over how it is built.</summary>
    public MafLabsHost AddAgent(string name, Func<IChatClient, AIAgent> factory, string? description = null, string[]? toolNames = null)
    {
        _agents[name] = (description, factory, toolNames ?? []);
        return this;
    }

    public async Task<int> RunAsync()
    {
        try
        {
            if (Options.List)
            {
                foreach (var (agentName, entry) in _agents) Console.WriteLine($"agent     {agentName,-24} dotnet       {entry.Description}");
                return 0;
            }
            if (_agents.Count == 0) throw new InvalidOperationException("no agents registered (call host.AddAgent before RunAsync)");

            var (client, info) = Providers.Create(Options.Provider, Options.Model);
            var name = ResolveTarget();
            var registration = _agents[name];
            var runner = new AgentRunner(registration.Factory(client), name, info, registration.Tools);
            await runner.ResetAsync();

            if (Options.Stdio) return await ServeStdioAsync(runner);
            if (Options.Prompt is not null)
            {
                var prompt = Options.Prompt == "-" ? await Console.In.ReadToEndAsync() : Options.Prompt;
                return await RunOnceAsync(runner, prompt);
            }
            return await InteractiveAsync(runner);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"error: {ex.GetType().Name}: {ex.Message}");
            return 2;
        }
    }

    private string ResolveTarget()
    {
        if (Options.Target is { } t && _agents.ContainsKey(t)) return t;
        if (_agents.Count == 1) return _agents.Keys.First(); // e.g. mafx passes the manifest name "greeter-dotnet"
        if (Options.Target is null) return _agents.Keys.First();
        throw new ArgumentException($"no agent '{Options.Target}'; registered: {string.Join(", ", _agents.Keys)}");
    }

    private async Task<int> RunOnceAsync(AgentRunner runner, string prompt)
    {
        var events = new List<JsonObject>();
        await foreach (var e in runner.TurnAsync(prompt))
        {
            events.Add(e);
            if (Options.Output == "jsonl") Console.WriteLine(e.ToJsonString());
            else if (Options.Output == "text" && !Options.Quiet) Plain(e);
        }
        var done = events.LastOrDefault() ?? new JsonObject();
        if (Options.Output == "text") Console.WriteLine(done["text"]?.GetValue<string>() ?? "");
        if (Options.Output == "json")
        {
            var arr = new JsonArray(events.Select(x => (JsonNode)x.DeepClone()).ToArray());
            Console.WriteLine(new JsonObject { ["info"] = runner.Info(), ["result"] = done.DeepClone(), ["events"] = arr }
                .ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
        }
        return done["ok"]?.GetValue<bool>() == true ? 0 : 1;
    }

    private static async Task<int> InteractiveAsync(AgentRunner runner)
    {
        Console.Error.WriteLine($"{runner.Name} ({runner.Provider.Provider} · {runner.Provider.Model}) — /exit to quit, /reset for a new session. Use `mafx run` for the rich UI.");
        while (true)
        {
            Console.Error.Write("› ");
            var line = Console.ReadLine();
            if (line is null || line.Trim() is "/exit" or "/quit") return 0;
            if (line.Trim() == "/reset") { await runner.ResetAsync(); continue; }
            if (string.IsNullOrWhiteSpace(line)) continue;
            await foreach (var e in runner.TurnAsync(line))
            {
                if (e["type"]!.GetValue<string>() == "text_delta") Console.Write(e["text"]!.GetValue<string>());
                else Plain(e);
            }
            Console.WriteLine();
        }
    }

    /// <summary>JSONL protocol: in {"type":"user","text"} | {"type":"reset"} | {"type":"exit"}; out ready + events.</summary>
    private static async Task<int> ServeStdioAsync(AgentRunner runner)
    {
        Console.Out.Flush();
        void Send(JsonObject o) { Console.WriteLine(o.ToJsonString()); Console.Out.Flush(); }

        Send(Events.Create("ready", ("info", runner.Info())));
        while (await Console.In.ReadLineAsync() is { } line)
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            JsonNode? msg;
            try { msg = JsonNode.Parse(line); }
            catch (JsonException) { Send(Events.Create("error", ("message", "invalid JSON"))); continue; }
            switch (msg?["type"]?.GetValue<string>())
            {
                case "exit":
                    return 0;
                case "reset":
                    await runner.ResetAsync();
                    Send(Events.Create("reset_done"));
                    break;
                case "user":
                    await foreach (var e in runner.TurnAsync(msg["text"]?.GetValue<string>() ?? "")) Send(e);
                    break;
                default:
                    Send(Events.Create("error", ("message", $"unknown message type: {msg?["type"]}")));
                    break;
            }
        }
        return 0;
    }

    private static void Plain(JsonObject e)
    {
        var err = Console.Error;
        switch (e["type"]!.GetValue<string>())
        {
            case "reasoning_delta": err.Write(e["text"]!.GetValue<string>()); break;
            case "tool_call": err.WriteLine($"\n⏺ {e["name"]}({e["arguments"]?.ToJsonString()})  [{e["call_id"]}]"); break;
            case "tool_result": err.WriteLine($"  ⎿ {(e["error"] is { } x ? x.ToString() : e["result"]?.ToJsonString())}"); break;
            case "error": err.WriteLine($"\nerror: {e["message"]}"); break;
            case "turn_completed":
                err.WriteLine($"\n── {e["model_calls"]} model calls · {e["tool_calls"]} tool calls · in {e["input_tokens"]} / out {e["output_tokens"]} tok · {e["duration_s"]}s ──");
                break;
        }
    }
}

internal sealed class AgentRunner(AIAgent agent, string name, ProviderInfo provider, string[] toolNames)
{
    private AgentSession? _session;

    public string Name => name;
    public ProviderInfo Provider => provider;

    public JsonObject Info() => new()
    {
        ["target"] = name,
        ["kind"] = "agent",
        ["runtime"] = "dotnet",
        ["provider"] = provider.Provider,
        ["model"] = provider.Model,
        ["api"] = provider.Api,
        ["agent_name"] = agent.Name,
        ["tools"] = new JsonArray(toolNames.Select(t => (JsonNode)JsonValue.Create(t)!).ToArray()),
        ["instructions"] = agent.GetService<ChatClientAgent>()?.Instructions,
    };

    public async Task ResetAsync() => _session = await agent.CreateSessionAsync();

    public async IAsyncEnumerable<JsonObject> TurnAsync(string text)
    {
        var sw = Stopwatch.StartNew();
        var tr = new UpdateTranslator();
        var events = new List<JsonObject>();
        var ok = true;
        await using var updates = agent.RunStreamingAsync(text, _session).GetAsyncEnumerator();
        while (true)
        {
            AgentResponseUpdate update;
            try
            {
                if (!await updates.MoveNextAsync()) break;
                update = updates.Current;
            }
            catch (Exception ex)
            {
                ok = false;
                events.Add(Events.Create("error", ("message", $"{ex.GetType().Name}: {ex.Message}")));
                break;
            }
            foreach (var e in tr.Translate(update)) yield return e;
        }
        foreach (var e in events) yield return e;
        yield return tr.Completed(sw, ok);
    }
}
