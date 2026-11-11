"""Counterfactual Level-2 queue tracking without changing the historical book."""

from dataclasses import dataclass, field

from .events import BookEvent, direction, integer
from .execution import Fill


@dataclass
class PassiveOrder:
    side: str
    price: int
    original_quantity: int
    quantity_ahead: int
    cancellations_ahead: bool = True
    remaining_quantity: int = field(init=False)
    fills: list[tuple[int, Fill]] = field(default_factory=list, init=False)
    status: str = field(default="OPEN", init=False)
    traded_ahead: int = field(default=0, init=False)
    cancelled_ahead: int = field(default=0, init=False)

    def __post_init__(self):
        direction(self.side)
        integer(self.price, "price", 1)
        integer(self.original_quantity, "order quantity", 1)
        integer(self.quantity_ahead, "quantity ahead")
        self.remaining_quantity = self.original_quantity

    @classmethod
    def join(cls, book, side, price, quantity, cancellations_ahead=True):
        direction(side)
        opposite = book.best_ask if side == "BUY" else book.best_bid
        if opposite is not None and (price >= opposite if side == "BUY" else price <= opposite):
            raise ValueError("passive order must not cross the opposite quote")
        levels = book.bids if side == "BUY" else book.asks
        return cls(side, price, quantity, levels.get(price, 0), cancellations_ahead)

    @property
    def filled_quantity(self):
        return self.original_quantity - self.remaining_quantity

    def cancel(self):
        if self.status != "FILLED":
            self.status = "CANCELLED"

    def update(self, event: BookEvent, event_index: int):
        """Apply eligible same-level flow; filled/cancelled orders leave the active queue."""
        if self.status in ("FILLED", "CANCELLED"):
            return
        book_side = "BID" if self.side == "BUY" else "ASK"
        if event.side != book_side or event.price != self.price or event.event_type == "ADD":
            return
        if event.event_type == "CANCEL" and not self.cancellations_ahead:
            return
        ahead = min(self.quantity_ahead, event.quantity)
        self.quantity_ahead -= ahead
        if event.event_type == "CANCEL":
            self.cancelled_ahead += ahead
            return
        self.traded_ahead += ahead
        filled = min(self.remaining_quantity, event.quantity - ahead)
        if filled:
            self.remaining_quantity -= filled
            self.fills.append((event_index, Fill(self.price, filled)))
            self.status = "FILLED" if not self.remaining_quantity else "PARTIAL"
