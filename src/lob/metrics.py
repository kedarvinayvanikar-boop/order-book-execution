"""Market and execution metrics; prices and costs are expressed in currency units."""

from .events import direction


def book_metrics(book) -> dict:
    bid, ask = book.best_bid, book.best_ask
    bq, aq = book.bids.get(bid, 0), book.asks.get(ask, 0)
    total = bq + aq
    two_sided = bid is not None and ask is not None
    return {
        "best_bid": bid / 100 if bid is not None else None,
        "best_ask": ask / 100 if ask is not None else None,
        "bid_quantity": bq,
        "ask_quantity": aq,
        "spread": (ask - bid) / 100 if two_sided else None,
        "midpoint": (bid + ask) / 200 if two_sided else None,
        "imbalance": (bq - aq) / total if total else None,
        "microprice": (bid * aq + ask * bq) / total / 100 if two_sided else None,
    }


def slippage(side, average_price, benchmark):
    sign = direction(side)
    return sign * (average_price - benchmark) if None not in (average_price, benchmark) else None


def relative_cost(cost, benchmark, scale=10000):
    return cost / benchmark * scale if cost is not None and benchmark not in (None, 0) else None


def execution_metrics(side, execution, before, after) -> dict:
    cost = slippage(side, execution.average_price, before["midpoint"])
    impact = slippage(side, after["midpoint"], before["midpoint"])
    return {
        "benchmark_midpoint": before["midpoint"],
        "slippage": cost,
        "slippage_percentage": relative_cost(cost, before["midpoint"], 100),
        "slippage_bps": relative_cost(cost, before["midpoint"]),
        "spread_cost_percentage": relative_cost(
            before["spread"] / 2 if before["spread"] is not None else None, before["midpoint"], 100
        ),
        "price_impact_percentage": relative_cost(impact, before["midpoint"], 100),
    }


def adverse_selection(side, fill_midpoint, future_midpoint):
    """Positive means adverse: midpoint falls after a BUY or rises after a SELL."""
    move = slippage(side, future_midpoint, fill_midpoint)
    return -move if move is not None else None
