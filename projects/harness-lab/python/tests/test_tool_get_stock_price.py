from harness_lab.tools.get_stock_price import get_stock_price


async def test_known_symbol():
    result = await get_stock_price.invoke(arguments={"symbol": "msft"}, skip_parsing=True)
    assert result["symbol"] == "MSFT" and result["price"] == 462.97


async def test_unknown_symbol_is_deterministic():
    first = await get_stock_price.invoke(arguments={"symbol": "ZZZ"}, skip_parsing=True)
    second = await get_stock_price.invoke(arguments={"symbol": "ZZZ"}, skip_parsing=True)
    assert first["price"] == second["price"] and 50 <= first["price"] < 500
