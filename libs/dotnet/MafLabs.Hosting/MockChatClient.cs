using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Extensions.AI;

namespace MafLabs.Hosting;

/// <summary>
/// Offline, deterministic chat client — same behaviour as the python mock: a short reasoning block, then
/// either tool calls (prompt lines like <c>call:get_weather {"city":"Paris"}</c>) or an echo.
/// </summary>
public sealed partial class MockChatClient(string model) : IChatClient
{
    [GeneratedRegex(@"^\s*call:(?<name>[\w\-.]+)\s*(?<args>\{.*\})?\s*$", RegexOptions.Multiline)]
    private static partial Regex CallRegex();

    private List<AIContent> Plan(IEnumerable<ChatMessage> messages)
    {
        var list = messages.ToList();
        var last = list.LastOrDefault();
        var results = last?.Contents.OfType<FunctionResultContent>().ToList() ?? [];
        if (results.Count > 0)
        {
            var lines = results.Select(r => $"- `{r.CallId}` → {JsonSerializer.Serialize(r.Result)}");
            return
            [
                new TextReasoningContent($"Received {results.Count} tool result(s); summarising."),
                new TextContent("[mock] Tool results:\n" + string.Join("\n", lines)),
            ];
        }

        var user = list.LastOrDefault(m => m.Role == ChatRole.User)?.Text ?? "";
        var calls = CallRegex().Matches(user);
        if (calls.Count > 0)
        {
            var contents = new List<AIContent> { new TextReasoningContent($"The prompt asks for {calls.Count} tool call(s).") };
            foreach (Match c in calls)
            {
                var json = c.Groups["args"].Success ? c.Groups["args"].Value : "{}";
                var args = JsonSerializer.Deserialize<Dictionary<string, object?>>(json) ?? new Dictionary<string, object?>();
                contents.Add(new FunctionCallContent($"call_{Guid.NewGuid():N}"[..13], c.Groups["name"].Value, args));
            }
            return contents;
        }

        return
        [
            new TextReasoningContent("No tool needed; echoing the user message."),
            new TextContent($"[mock] {user}"),
        ];
    }

    private static UsageContent Usage(IEnumerable<ChatMessage> messages, List<AIContent> contents) => new(new UsageDetails
    {
        InputTokenCount = messages.Sum(m => (m.Text ?? "").Split(' ', StringSplitOptions.RemoveEmptyEntries).Length),
        OutputTokenCount = contents.Sum(c => c is TextContent t ? t.Text.Split(' ').Length : c is TextReasoningContent r ? r.Text.Split(' ').Length : 1),
    });

    public Task<ChatResponse> GetResponseAsync(IEnumerable<ChatMessage> messages, ChatOptions? options = null, CancellationToken cancellationToken = default)
    {
        var contents = Plan(messages);
        contents.Add(Usage(messages, contents));
        return Task.FromResult(new ChatResponse(new ChatMessage(ChatRole.Assistant, contents)) { ModelId = model });
    }

    public async IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(IEnumerable<ChatMessage> messages, ChatOptions? options = null,
        [EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        var contents = Plan(messages);
        var responseId = $"mock_{Guid.NewGuid():N}"[..13];
        foreach (var content in contents)
        {
            if (content is TextContent or TextReasoningContent)
            {
                var text = content is TextContent t ? t.Text : ((TextReasoningContent)content).Text;
                var words = text.Split(' ');
                for (var i = 0; i < words.Length; i++)
                {
                    var piece = i == words.Length - 1 ? words[i] : words[i] + " ";
                    AIContent delta = content is TextContent ? new TextContent(piece) : new TextReasoningContent(piece);
                    yield return new ChatResponseUpdate(ChatRole.Assistant, [delta]) { ResponseId = responseId, ModelId = model };
                    await Task.Yield();
                }
            }
            else
            {
                yield return new ChatResponseUpdate(ChatRole.Assistant, [content]) { ResponseId = responseId, ModelId = model };
            }
        }
        yield return new ChatResponseUpdate(ChatRole.Assistant, [Usage(messages, contents)]) { ResponseId = responseId, ModelId = model };
    }

    public object? GetService(Type serviceType, object? serviceKey = null) =>
        serviceKey is null && serviceType.IsInstanceOfType(this) ? this : null;

    public void Dispose() { }
}
