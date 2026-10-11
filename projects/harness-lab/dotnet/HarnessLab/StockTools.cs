using System.ComponentModel;

namespace HarnessLab;

/// <summary>Illustrative stock prices (mock data, not real quotes) — same price book as the official claw sample.</summary>
public static class StockTools
{
    public sealed record StockQuote(string Symbol, decimal Price, string Currency, DateTimeOffset AsOf);

    private static readonly Dictionary<string, decimal> PriceBook = new(StringComparer.OrdinalIgnoreCase)
    {
        ["MSFT"] = 462.97m,
        ["AAPL"] = 229.35m,
        ["GOOGL"] = 178.12m,
        ["AMZN"] = 201.45m,
        ["NVDA"] = 134.81m,
    };

    [Description("Gets the latest (delayed, illustrative) stock price for a ticker symbol.")]
    public static StockQuote GetStockPrice([Description("The stock ticker symbol, e.g. MSFT or AAPL.")] string symbol)
    {
        var ticker = symbol.Trim().ToUpperInvariant();
        if (!PriceBook.TryGetValue(ticker, out var price))
        {
            // Deterministic pseudo-price for unknown symbols so runs are repeatable.
            var seed = 0;
            foreach (var ch in ticker) seed = (seed * 31 + ch) % 1_000_000;
            price = 50m + seed % 45000 / 100m;
        }
        return new StockQuote(ticker, price, "USD", DateTimeOffset.UtcNow);
    }
}
