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

    /// <summary>Workspace root (the folder with maf-labs.yaml), or null when run outside the workspace.</summary>
    public string? WorkspaceRoot => Env.WorkspaceRoot;

    /// <summary>The provider this run will use (--provider, MAF_PROVIDER, maf-labs.yaml defaults, then sglang).</summary>
    public string Provider => Providers.Resolve(Options.Provider);

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

            if (Options.Effort is { } requested) Providers.ParseEffort(requested); // fail fast on a bad value
            var effort = new EffortSetting(Options.Effort);
            var (client, info) = Providers.Create(Options.Provider, Options.Model, () => effort.Value);
            var name = ResolveTarget();
            var registration = _agents[name];
            var runner = new AgentRunner(registration.Factory(client), name, info, registration.Tools, effort);
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
        var stream = runner.TurnAsync(prompt);
        for (var round = 0; round <= 25; round++)
        {
            await foreach (var e in stream)
            {
                events.Add(e);
                if (Options.Output == "jsonl") Console.WriteLine(e.ToJsonString());
                else if (Options.Output == "text" && !Options.Quiet) Plain(e);
            }
            if (runner.Pending.Count == 0) break;
            // Standalone -p: approve everything with --yes, otherwise deny (mafx relays decisions itself).
            var decision = Options.Yes ? "approve" : "deny";
            stream = runner.ApproveAsync(runner.Pending.ToDictionary(r => r.RequestId, _ => decision));
        }
        var done = events.LastOrDefault() ?? new JsonObject();
        if (Options.Output == "text") Console.WriteLine((done["text"]?.GetValue<string>() ?? "").Trim());
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
                case "approve":
                    var decisions = new Dictionary<string, string>();
                    if (msg["decisions"] is JsonObject map)
                    {
                        foreach (var (id, value) in map) decisions[id] = value?.GetValue<string>() ?? "deny";
                    }
                    await foreach (var e in runner.ApproveAsync(decisions)) Send(e);
                    break;
                case "set_effort":
                    var requested = msg["effort"]?.GetValue<string>();
                    try
                    {
                        if (requested is not null) Providers.ParseEffort(requested);
                        runner.Effort.Value = requested;
                        Send(Events.Create("effort_set", ("effort", requested ?? "default")));
                    }
                    catch (ArgumentException ex)
                    {
                        Send(Events.Create("error", ("message", ex.Message)));
                    }
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
            case "approval_request": err.WriteLine($"\n🔐 approval needed: {e["name"]}({e["arguments"]?.ToJsonString()})"); break;
            case "approval_decision": err.WriteLine($"  {e["decision"]}: {e["name"]}"); break;
            case "error": err.WriteLine($"\nerror: {e["message"]}"); break;
            case "turn_completed":
                err.WriteLine($"\n── {e["model_calls"]} model calls · {e["tool_calls"]} tool calls · in {e["input_tokens"]} / out {e["output_tokens"]} tok · {e["duration_s"]}s ──");
                break;
        }
    }
}

/// <summary>The reasoning effort for the following model calls; null means the server default.</summary>
internal sealed class EffortSetting(string? value)
{
    public string? Value { get; set; } = value;
}

internal sealed class AgentRunner(AIAgent agent, string name, ProviderInfo provider, string[] toolNames, EffortSetting effort)
{
    public EffortSetting Effort => effort;

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
        ["effort"] = effort.Value ?? "default",
        ["agent_name"] = agent.Name,
        ["tools"] = new JsonArray(toolNames.Select(t => (JsonNode)JsonValue.Create(t)!).ToArray()),
        ["instructions"] = agent.GetService<ChatClientAgent>()?.Instructions,
    };

    /// <summary>Approval requests from the last turn.</summary>
    public List<ToolApprovalRequestContent> Pending { get; private set; } = [];

    public async Task ResetAsync()
    {
        _session = await agent.CreateSessionAsync();
        Pending = [];
    }

    public IAsyncEnumerable<JsonObject> TurnAsync(string text) => RunAsync(new ChatMessage(ChatRole.User, text), []);

    /// <summary>
    /// Answers the pending approval requests (approve | deny | always | always_args; missing ids are denied)
    /// and continues the turn.
    /// </summary>
    public IAsyncEnumerable<JsonObject> ApproveAsync(IReadOnlyDictionary<string, string> decisions)
    {
        var responses = new List<AIContent>();
        var decided = new List<JsonObject>();
        foreach (var request in Pending)
        {
            var decision = decisions.TryGetValue(request.RequestId, out var d) ? d : "deny";
            responses.Add(decision switch
            {
                "approve" => request.CreateResponse(approved: true, reason: "User approved"),
                "always" => request.CreateAlwaysApproveToolResponse("Approved for this session"),
                "always_args" => request.CreateAlwaysApproveToolWithArgumentsResponse("Approved for these arguments"),
                "deny" => request.CreateResponse(approved: false, reason: "User denied"),
                _ => throw new ArgumentException($"unknown approval decision '{decision}'"),
            });
            decided.Add(Events.Create("approval_decision", ("request_id", request.RequestId),
                ("name", (request.ToolCall as FunctionCallContent)?.Name), ("decision", decision)));
        }
        Pending = [];
        return RunAsync(new ChatMessage(ChatRole.User, responses), decided);
    }

    private async IAsyncEnumerable<JsonObject> RunAsync(ChatMessage message, List<JsonObject> preamble)
    {
        foreach (var e in preamble) yield return e;
        var sw = Stopwatch.StartNew();
        var tr = new UpdateTranslator();
        var events = new List<JsonObject>();
        var ok = true;
        await using var updates = agent.RunStreamingAsync(message, _session).GetAsyncEnumerator();
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
                var detail = Env.Get("MAFX_DEBUG") is null ? $"{ex.GetType().Name}: {ex.Message}" : ex.ToString();
                events.Add(Events.Create("error", ("message", detail)));
                break;
            }
            foreach (var e in tr.Translate(update)) yield return e;
        }
        foreach (var e in events) yield return e;
        Pending = tr.ApprovalRequests;
        yield return tr.Completed(sw, ok);
    }
}
