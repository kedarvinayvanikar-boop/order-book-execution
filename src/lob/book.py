"""Aggregate price-level book. Updates are in-place; snapshots own their data."""

from collections.abc import Iterable

from .events import BookEvent, integer, price_ticks


class OrderBook:
    def __init__(self, bids: dict[int, int] | None = None, asks: dict[int, int] | None = None):
        self.bids = self._levels(bids or {})
        self.asks = self._levels(asks or {})

    @staticmethod
    def _levels(levels):
        result = {}
        for price, quantity in levels.items():
            integer(price, "price ticks", 1)
            integer(quantity, "quantity")
            if quantity:
                result[price] = quantity
        return result

    @classmethod
    def from_dict(cls, book: dict) -> "OrderBook":
        return cls(
            {price_ticks(p): q for p, q in book["Bids"].items()},
            {price_ticks(p): q for p, q in book["Asks"].items()},
        )

    def copy(self) -> "OrderBook":
        return OrderBook(self.bids, self.asks)

    def snapshot(self) -> dict:
        return {"bids": self.bids.copy(), "asks": self.asks.copy()}

    @property
    def best_bid(self) -> int | None:
        return max(self.bids, default=None)

    @property
    def best_ask(self) -> int | None:
        return min(self.asks, default=None)

    def apply(self, event: BookEvent | dict) -> None:
        if isinstance(event, dict):
            event = BookEvent.from_dict(event)
        levels = self.bids if event.side == "BID" else self.asks
        current = levels.get(event.price, 0)
        if event.event_type == "ADD":
            quantity = integer(current + event.quantity, "level quantity")
        else:
            if event.price not in levels or event.quantity > current:
                raise ValueError("removal exceeds resting liquidity or level is absent")
            quantity = current - event.quantity
        if quantity:
            levels[event.price] = quantity
        else:
            levels.pop(event.price, None)

    def replay(self, events: Iterable[BookEvent]) -> list[dict]:
        history = [self.snapshot()]
        for event in events:
            self.apply(event)
            history.append(self.snapshot())
        return history
