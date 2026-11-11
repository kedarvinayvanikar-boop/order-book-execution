import math

import pytest

from lob import BookEvent, OrderBook
from lob.events import price_ticks
from lob.metrics import book_metrics


def test_reference_metrics_and_snapshot_isolation():
    book = OrderBook.from_dict({"Bids": {50: 750}, "Asks": {50.04: 250}})
    metrics = book_metrics(book)
    assert metrics["spread"] == pytest.approx(0.04)
    assert metrics["midpoint"] == 50.02
    assert metrics["imbalance"] == 0.5
    assert metrics["microprice"] == 50.03
    history = book.replay(
        [BookEvent("ADD", "BID", 5001, 100), BookEvent("TRADE", "ASK", 5004, 250)]
    )
    assert 5001 not in history[0]["bids"]
    assert history[1]["asks"] == {5004: 250}
    assert history[2]["asks"] == {}
    assert book_metrics(book)["midpoint"] is None
    assert book_metrics(book)["imbalance"] == 1


@pytest.mark.parametrize("side", ["BID", "ASK"])
@pytest.mark.parametrize("kind", ["CANCEL", "TRADE"])
def test_removal_validation_and_deletion(side, kind):
    book = OrderBook({5000: 10}, {5004: 10})
    price = 5000 if side == "BID" else 5004
    original = book.snapshot()
    for p, q in [(price, 11), (price - 1, 1)]:
        with pytest.raises(ValueError):
            book.apply(BookEvent(kind, side, p, q))
        assert book.snapshot() == original
    book.apply(BookEvent(kind, side, price, 4))
    book.apply(BookEvent(kind, side, price, 6))
    assert price not in (book.bids if side == "BID" else book.asks)


@pytest.mark.parametrize(
    "kind,side,price,quantity",
    [
        ("BAD", "BID", 5000, 1),
        ("ADD", "BUY", 5000, 1),
        ("ADD", "BID", 0, 1),
        ("ADD", "BID", 5000, -1),
        ("ADD", "BID", 5000, 1.5),
        ("ADD", "BID", 5000, True),
    ],
)
def test_invalid_events(kind, side, price, quantity):
    with pytest.raises(ValueError):
        BookEvent(kind, side, price, quantity)


@pytest.mark.parametrize("price", [math.nan, math.inf, -1, 50.001, "garbage"])
def test_invalid_prices(price):
    with pytest.raises(ValueError):
        price_ticks(price)


def test_empty_and_zero_add_and_legacy_adapter():
    book = OrderBook()
    assert book.best_bid is book.best_ask is None
    assert book_metrics(book)["imbalance"] is None
    book.apply({"Type": "ADD", "Side": "BID", "Price": 50.0, "Quantity": 0})
    assert not book.bids
    book.apply({"Type": "ADD", "Side": "BID", "Price": 50.0, "Quantity": 10})
    book.apply(BookEvent("ADD", "BID", 4999, 100))
    book.apply(BookEvent("ADD", "BID", 5000, 2))
    assert book.best_bid == 5000 and book.bids[5000] == 12
    with pytest.raises(ValueError):
        book.apply({"Type": "ADD"})
