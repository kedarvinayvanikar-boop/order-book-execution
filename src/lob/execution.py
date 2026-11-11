"""Aggressive execution against a mutable aggregate book."""

from dataclasses import dataclass

from .events import direction, integer
from .metrics import book_metrics, execution_metrics


@dataclass(frozen=True)
class Fill:
    price: int
    quantity: int


@dataclass(frozen=True)
class ExecutionResult:
    requested_quantity: int
    filled_quantity: int
    remaining_quantity: int
    average_price: float | None
    fills: tuple[Fill, ...]

    @property
    def levels_consumed(self):
        """Number of distinct levels touched, including a partially depleted level."""
        return len(self.fills)

    @property
    def worst_fill_price(self):
        return self.fills[-1].price / 100 if self.fills else None


def execute_market_order(book, side: str, quantity: int) -> ExecutionResult:
    direction(side)
    integer(quantity, "quantity")
    levels = book.asks if side == "BUY" else book.bids
    remaining, fills = quantity, []
    for price in sorted(levels, reverse=side == "SELL"):
        if not remaining:
            break
        filled = min(remaining, levels[price])
        fills.append(Fill(price, filled))
        remaining -= filled
        levels[price] -= filled
        if not levels[price]:
            del levels[price]
    filled = quantity - remaining
    average = sum(f.price * f.quantity for f in fills) / filled / 100 if filled else None
    return ExecutionResult(quantity, filled, remaining, average, tuple(fills))


def analyze_market_order(book, side, quantity):
    before = book_metrics(book)
    result = execute_market_order(book, side, quantity)
    return result, execution_metrics(side, result, before, book_metrics(book))
