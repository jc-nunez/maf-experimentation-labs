using System.ComponentModel;

namespace HelloWorld.Tools;

/// <summary>Deterministic fake weather tool (same data as the python tool).</summary>
public static class Weather
{
    private static readonly Dictionary<string, (string Forecast, int TempC)> Forecasts = new(StringComparer.OrdinalIgnoreCase)
    {
        ["paris"] = ("sunny", 22),
        ["lisbon"] = ("cloudy", 19),
        ["seattle"] = ("rain", 12),
    };

    [Description("Get the current weather for a city.")]
    public static object GetWeather([Description("City name, e.g. 'Paris'")] string city)
    {
        var (forecast, temp) = Forecasts.TryGetValue(city.Trim(), out var f) ? f : ("partly cloudy", 18);
        return new { city, forecast, temp_c = temp };
    }
}
