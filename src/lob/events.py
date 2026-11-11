"""Validated event boundary, including the exploratory dictionary format."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

TICK_SIZE = Decimal("0.01")
MAX_INTEGER = 2**63 - 1


def integer(value: int, name: str, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= MAX_INTEGER:
        raise ValueError(f"{name} must be an integer in [{minimum}, {MAX_INTEGER}]")
    return value


def price_ticks(price: float) -> int:
    try:
        ticks = Decimal(str(price)) / TICK_SIZE
        if not ticks.is_finite() or ticks != ticks.to_integral_value():
            raise ValueError("price must be finite and aligned to the 0.01 tick")
        return integer(int(ticks), "price ticks", 1)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("invalid price") from exc


def direction(side: str) -> int:
    if side not in ("BUY", "SELL"):
        raise ValueError("order side must be BUY or SELL")
    return 1 if side == "BUY" else -1


@dataclass(frozen=True)
class BookEvent:
    event_type: str
    side: str
    price: int
    quantity: int
    timestamp: int = 0

    def __post_init__(self):
        if self.event_type not in ("ADD", "CANCEL", "TRADE"):
            raise ValueError("unknown event type")
        if self.side not in ("BID", "ASK"):
            raise ValueError("book side must be BID or ASK")
        integer(self.price, "price ticks", 1)
        integer(self.quantity, "quantity")
        integer(self.timestamp, "timestamp")

    @classmethod
    def from_dict(cls, event: dict) -> "BookEvent":
        """Convert capitalized keys and currency prices to validated tick units."""
        try:
            return cls(
                event["Type"],
                event["Side"],
                price_ticks(event["Price"]),
                event["Quantity"],
                event.get("Timestamp", 0),
            )
        except KeyError as exc:
            raise ValueError(f"missing event field: {exc.args[0]}") from exc
