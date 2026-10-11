using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace MafLabs.Hosting;

/// <summary>Builds trajectory events with the same shape as maf_labs_host.events (docs/host-protocol.md).</summary>
public static class Events
{
    public static JsonObject Create(string type, params (string Key, JsonNode? Value)[] fields)
    {
        var e = new JsonObject
        {
            ["type"] = type,
            ["ts"] = Math.Round(DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0, 3),
        };
        foreach (var (k, v) in fields) e[k] = v;
        return e;
    }

    public static JsonNode? ToNode(object? value)
    {
        if (value is null) return null;
        if (value is JsonNode n) return n.DeepClone();
        if (value is JsonElement el) return JsonNode.Parse(el.GetRawText());
        if (value is string s)
        {
            try { return JsonNode.Parse(s); } catch (JsonException) { return JsonValue.Create(s); }
        }
        try { return JsonSerializer.SerializeToNode(value); }
        catch (Exception) { return JsonValue.Create(value.ToString()); }
    }
}

/// <summary>Turns AgentResponseUpdate streams into trajectory events and keeps turn totals.</summary>
public sealed class UpdateTranslator
{
    private readonly Dictionary<string, Stopwatch> _calls = new();
    private readonly System.Text.StringBuilder _text = new();

    public long InputTokens { get; private set; }
    public long OutputTokens { get; private set; }
    public int ModelCalls { get; private set; }
    public int ToolCalls { get; private set; }
    public string Text => _text.ToString();

    /// <summary>Tool calls waiting for approval in this turn (answered through AgentRunner.ApproveAsync).</summary>
    public List<ToolApprovalRequestContent> ApprovalRequests { get; } = [];

    public IEnumerable<JsonObject> Translate(AgentResponseUpdate update)
    {
        foreach (var content in update.Contents)
        {
            switch (content)
            {
                case TextReasoningContent r when !string.IsNullOrEmpty(r.Text):
                    yield return Events.Create("reasoning_delta", ("text", r.Text));
                    break;
                case TextContent t when !string.IsNullOrEmpty(t.Text):
                    _text.Append(t.Text);
                    yield return Events.Create("text_delta", ("text", t.Text));
                    break;
                case FunctionCallContent call:
                    ToolCalls++;
                    _calls[call.CallId] = Stopwatch.StartNew();
                    yield return Events.Create("tool_call", ("call_id", call.CallId), ("name", call.Name),
                        ("arguments", Events.ToNode(call.Arguments) ?? new JsonObject()));
                    break;
                case FunctionResultContent result:
                    double? took = _calls.Remove(result.CallId, out var sw) ? Math.Round(sw.Elapsed.TotalSeconds, 3) : null;
                    yield return Events.Create("tool_result", ("call_id", result.CallId), ("result", Events.ToNode(result.Result)),
                        ("error", result.Exception?.Message), ("duration_s", took));
                    break;
                case UsageContent usage:
                    ModelCalls++;
                    InputTokens += usage.Details.InputTokenCount ?? 0;
                    OutputTokens += usage.Details.OutputTokenCount ?? 0;
                    yield return Events.Create("usage", ("input_tokens", usage.Details.InputTokenCount ?? 0),
                        ("output_tokens", usage.Details.OutputTokenCount ?? 0));
                    break;
                case ToolApprovalRequestContent approval:
                    ApprovalRequests.Add(approval);
                    var approvalCall = approval.ToolCall as FunctionCallContent;
                    yield return Events.Create("approval_request", ("request_id", approval.RequestId),
                        ("call_id", approval.ToolCall.CallId), ("name", approvalCall?.Name),
                        ("arguments", Events.ToNode(approvalCall?.Arguments) ?? new JsonObject()));
                    break;
                case ErrorContent error:
                    yield return Events.Create("error", ("message", error.Message), ("code", error.ErrorCode));
                    break;
            }
        }
    }

    public JsonObject Completed(Stopwatch elapsed, bool ok) => Events.Create("turn_completed",
        ("ok", ok), ("text", Text), ("duration_s", Math.Round(elapsed.Elapsed.TotalSeconds, 3)),
        ("input_tokens", InputTokens), ("output_tokens", OutputTokens),
        ("model_calls", ModelCalls), ("tool_calls", ToolCalls),
        ("pending_approvals", new JsonArray(ApprovalRequests.Select(r => (JsonNode)new JsonObject
        {
            ["request_id"] = r.RequestId,
            ["name"] = (r.ToolCall as FunctionCallContent)?.Name,
            ["arguments"] = Events.ToNode((r.ToolCall as FunctionCallContent)?.Arguments) ?? new JsonObject(),
        }).ToArray())));
}
