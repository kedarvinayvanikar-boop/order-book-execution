import pytest

from lob import OrderBook, execute_market_order
from lob.execution import analyze_market_order
from lob.metrics import adverse_selection, relative_cost, slippage


@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize("quantity", [0, 100, 600, 2000])
def test_market_walk(side, quantity):
    book = OrderBook({5000: 250, 4999: 300, 4998: 500}, {5004: 250, 5005: 300, 5006: 500})
    result = execute_market_order(book, side, quantity)
    assert result.filled_quantity == min(quantity, 1050)
    assert result.remaining_quantity == max(0, quantity - 1050)
    assert sum(f.quantity for f in result.fills) == result.filled_quantity
    if quantity == 600:
        assert [f.quantity for f in result.fills] == [250, 300, 50]
        prices = [5004, 5005, 5006] if side == "BUY" else [5000, 4999, 4998]
        assert result.average_price == pytest.approx(
            sum(p * q for p, q in zip(prices, [250, 300, 50])) / 60000
        )
        assert result.levels_consumed == 3
        assert result.worst_fill_price == prices[-1] / 100
    if quantity == 0:
        assert result.average_price is None


def test_metrics_and_empty_analysis():
    book = OrderBook({5000: 750}, {5004: 250, 5005: 300, 5006: 500})
    result, metrics = analyze_market_order(book, "BUY", 600)
    assert result.average_price == pytest.approx(50.0466666667)
    assert metrics["slippage_bps"] == pytest.approx(5.33120085299)
    assert metrics["spread_cost_percentage"] == pytest.approx(0.0399840064)
    assert metrics["price_impact_percentage"] == pytest.approx(0.0199920032)
    assert analyze_market_order(OrderBook(), "BUY", 10)[1]["slippage"] is None
    assert relative_cost(1, 0) is None
    assert slippage("SELL", 49.99, 50.02) == pytest.approx(0.03)
    assert adverse_selection("BUY", 50, 49.9) == pytest.approx(0.1)
    assert adverse_selection("SELL", 50, 50.1) == pytest.approx(0.1)
    for side, quantity in [("BAD", 1), ("BUY", -1), ("BUY", 1.5)]:
        with pytest.raises(ValueError):
            execute_market_order(book, side, quantity)
