"""Seeded, valid aggregate flow with depletion, replenishment, and quote changes."""

import random

from .book import OrderBook
from .events import BookEvent, integer


def initial_book():
    return OrderBook(
        {5000 - i: 200 + 100 * i for i in range(5)}, {5004 + i: 200 + 100 * i for i in range(5)}
    )


def generate_events(count=10000, seed=7):
    integer(count, "event count", 1)
    rng = random.Random(seed)
    book = initial_book()
    for index in range(count):
        side = rng.choice(("BID", "ASK"))
        levels = book.bids if side == "BID" else book.asks
        if not levels or rng.random() < 0.40:
            # A fixed instrument grid bounds the walk while allowing quote improvement.
            price = rng.randint(4996, 5002) if side == "BID" else rng.randint(5003, 5009)
            event = BookEvent("ADD", side, price, rng.randint(20, 200), index)
        else:
            price = (
                (max(levels) if side == "BID" else min(levels))
                if rng.random() < 0.8
                else rng.choice(list(levels))
            )
            kind = "TRADE" if rng.random() < 0.65 else "CANCEL"
            event = BookEvent(kind, side, price, rng.randint(1, levels[price]), index)
        book.apply(event)
        yield event
