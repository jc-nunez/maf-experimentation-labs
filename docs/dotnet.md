# .NET

Needs the .NET 10 SDK (`global.json`). Package versions are central in `Directory.Packages.props`. Current versions:
`Microsoft.Agents.AI` and `Microsoft.Agents.AI.OpenAI` 1.24.0, `Microsoft.Extensions.AI.OpenAI` 10.10.1, `OpenAI` 2.14.0.

```csharp
using MafLabs.Hosting;
using Microsoft.Extensions.AI;

var host = MafLabsHost.Create(args);           // loads .env, parses the shared arguments
host.AddAgent("greeter",
    instructions: "You are friendly.",
    tools: [AIFunctionFactory.Create(Weather.GetWeather, name: "get_weather")]);
// or full control:  host.AddAgent("custom", client => client.AsAIAgent(new ChatClientAgentOptions { … }));
return await host.RunAsync();                  // -p | interactive | --stdio
```

Two ways to write a .NET component, both supported by the manifest:
- **Project-based:** `dotnet/<Proj>/<Proj>.csproj` references `libs/dotnet/MafLabs.Hosting`. Manifest: `project: dotnet/<Proj>/<Proj>.csproj`.
- **Single-file app (.NET 10):** `dotnet/apps/<name>.cs` with `#:project ../../../../libs/dotnet/MafLabs.Hosting/MafLabs.Hosting.csproj` at the top. Manifest: `file: dotnet/apps/<name>.cs`. Keep these out of folders that contain a `.csproj`; the project would compile them too.

`mafx run <project>/<name>` starts the host with `dotnet run … -- --stdio <name>`, so .NET agents get the same
interactive UI, trajectory view and traces as Python ones. A host with a single registered agent serves it
whatever name the manifest uses.

Build everything with `dotnet build maf-labs.slnx`. On Ubuntu 24.04 the SDK is available from Microsoft's apt
repository (`dotnet-sdk-10.0`).
