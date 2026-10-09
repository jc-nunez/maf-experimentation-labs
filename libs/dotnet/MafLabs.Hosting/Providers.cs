using System.ClientModel;
using Microsoft.Extensions.AI;
using OpenAI;
using OpenAI.Responses;

namespace MafLabs.Hosting;

public sealed record ProviderInfo(string Provider, string? Model, string Api, string? BaseUrl = null);

/// <summary>Provider → IChatClient, mirroring maf_labs_host.providers (same environment variables).</summary>
public static class Providers
{
    public static readonly string[] Names = ["sglang", "openai", "azure-openai", "foundry", "mock"];

    public static (IChatClient Client, ProviderInfo Info) Create(string? provider, string? model)
    {
        var name = (provider ?? Env.Get("MAF_PROVIDER") ?? Env.DefaultProvider() ?? "sglang").ToLowerInvariant();
        switch (name)
        {
            case "mock":
                return (new MockChatClient(model ?? "mock-model"), new ProviderInfo("mock", model ?? "mock-model", "mock"));

            case "sglang":
            {
                var baseUrl = Env.Require("SGLANG_BASE_URL", name);
                var m = model ?? Env.Require("SGLANG_MODEL", name);
                var client = CreateOpenAIClient(baseUrl, Env.Get("SGLANG_API_KEY", "EMPTY")!);
                var api = (Env.Get("SGLANG_API", "responses") ?? "responses").ToLowerInvariant();
                if (api == "chat")
                {
                    return (client.GetChatClient(m).AsIChatClient(), new ProviderInfo(name, m, "chat", baseUrl));
                }
                // Self-hosted Responses servers rarely support stored responses: keep history client-side.
                var store = (Env.Get("SGLANG_STORE", "false") ?? "false").Equals("true", StringComparison.OrdinalIgnoreCase);
                var chat = store
                    ? client.GetResponsesClient().AsIChatClient(m)
                    : client.GetResponsesClient().AsIChatClientWithStoredOutputDisabled(m, includeReasoningEncryptedContent: false);
                return (chat, new ProviderInfo(name, m, "responses", baseUrl));
            }

            case "openai":
            {
                var m = model ?? Env.Require("OPENAI_MODEL", name);
                var client = new OpenAIClient(Env.Require("OPENAI_API_KEY", name));
                return (client.GetResponsesClient().AsIChatClient(m), new ProviderInfo(name, m, "responses"));
            }

            case "azure-openai":
            {
                // Azure OpenAI v1 endpoint is OpenAI-compatible: {endpoint}/openai/v1/ with an API key.
                // Entra ID auth is not wired in the .NET host yet (use the python host, or add Azure.Identity).
                var endpoint = Env.Require("AZURE_OPENAI_ENDPOINT", name).TrimEnd('/');
                var m = model ?? Env.Require("AZURE_OPENAI_DEPLOYMENT", name);
                var key = Env.Get("AZURE_OPENAI_API_KEY")
                    ?? throw new InvalidOperationException("the .NET host needs AZURE_OPENAI_API_KEY for azure-openai");
                var client = CreateOpenAIClient($"{endpoint}/openai/v1/", key);
                return (client.GetResponsesClient().AsIChatClient(m), new ProviderInfo(name, m, "responses", endpoint));
            }

            case "foundry":
                throw new NotSupportedException("provider 'foundry' is not wired in the .NET host yet; use the python host");

            default:
                throw new ArgumentException($"unknown provider '{name}'; choose one of {string.Join(", ", Names)}");
        }
    }

    private static OpenAIClient CreateOpenAIClient(string baseUrl, string apiKey) =>
        new(new ApiKeyCredential(apiKey), new OpenAIClientOptions { Endpoint = new Uri(baseUrl) });
}
