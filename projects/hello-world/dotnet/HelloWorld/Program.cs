using HelloWorld.Tools;
using MafLabs.Hosting;
using Microsoft.Extensions.AI;

// Shared host: provider/model from .env, -p (run once), interactive, --stdio (used by mafx).
var host = MafLabsHost.Create(args);

host.AddAgent(
    "greeter",
    instructions: """
        You are a friendly, concise assistant.
        When the user asks about the weather, call the get_weather tool for each city before answering.
        """,
    tools: [AIFunctionFactory.Create(Weather.GetWeather, name: "get_weather")],
    description: "Friendly assistant with weather lookup (.NET project)");

return await host.RunAsync();
