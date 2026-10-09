using HarnessLab;
using MafLabs.Hosting;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

// .NET port of the official "Build your own claw" step 1 sample (HarnessAgent):
// https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/Harness/BuildYourOwnClaw
// AsHarnessAgent wires function invocation, per-service-call history persistence, compaction, todos,
// plan/execute modes and file memory; we add finance instructions and the get_stock_price tool.
var host = MafLabsHost.Create(args);

const string Instructions = """
    ## Personal Finance Assistant Instructions

    You are a personal finance and investing assistant. You help the user understand their
    watchlist and the markets. When asked about a stock, look up its current price with the
    get_stock_price tool.

    ### Working style

    - Always verify numbers with a tool rather than relying on memory. Stock prices change.
    - Keep the user's watchlist in a memory file called watchlist.md: read it when reviewing the
      watchlist, and update it whenever the user adds or removes a ticker.
    - For multi-step requests, plan first: create todos, then switch to execute mode and work through them.

    ### Important

    You provide information and analysis only. You are not a licensed financial advisor and you
    must not present your output as personalized investment advice. Remind the user to do their
    own research before making decisions.
    """;

var memoryRoot = Path.Combine(host.WorkspaceRoot ?? Directory.GetCurrentDirectory(), ".mafx", "memory", "harness-lab");

host.AddAgent(
    "claw",
    client => client.AsHarnessAgent(new HarnessAgentOptions
    {
        Name = "claw",
        Description = "Personal finance assistant with planning, todos and file memory",
        ChatOptions = new ChatOptions
        {
            Instructions = Instructions,
            Tools = [AIFunctionFactory.Create(StockTools.GetStockPrice, name: "get_stock_price")],
        },
        // Qwen3.8-Flash-Next serves a 262K context; keep room for the response.
        MaxContextWindowTokens = 262_144,
        MaxOutputTokens = 16_384,
        // Hosted web search is an OpenAI/Foundry service tool; SGLang has no equivalent.
        DisableWebSearch = host.Provider is not ("openai" or "azure-openai" or "foundry"),
        // File memory under .mafx/ (gitignored) instead of ./agent-file-memory in the current directory.
        FileMemoryStore = new FileSystemAgentFileStore(memoryRoot),
    }),
    description: "Personal finance assistant on HarnessAgent",
    toolNames: ["get_stock_price"]);

return await host.RunAsync();
