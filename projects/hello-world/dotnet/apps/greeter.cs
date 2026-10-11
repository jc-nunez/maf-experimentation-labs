#:project ../../../../libs/dotnet/MafLabs.Hosting/MafLabs.Hosting.csproj
#:property PublishAot=false
// .NET 10 single-file app:  dotnet run greeter.cs -- -p "What's the weather in Paris?"
using System.ComponentModel;
using MafLabs.Hosting;
using Microsoft.Extensions.AI;

var host = MafLabsHost.Create(args);

host.AddAgent(
    "greeter",
    instructions: "You are a friendly, concise assistant. Use get_weather for weather questions.",
    tools: [AIFunctionFactory.Create(GetWeather, name: "get_weather")],
    description: "Friendly assistant with weather lookup (.NET single-file app)");

return await host.RunAsync();

[Description("Get the current weather for a city.")]
static object GetWeather([Description("City name")] string city) => new { city, forecast = "sunny", temp_c = 22 };
