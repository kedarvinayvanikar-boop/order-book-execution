import pytest

from lob import BookEvent, OrderBook
from lob.queue import PassiveOrder


@pytest.mark.parametrize("side,book_side,price", [("BUY", "BID", 5000), ("SELL", "ASK", 5004)])
def test_queue_flow(side, book_side, price):
    order = PassiveOrder.join(OrderBook({5000: 100}, {5004: 100}), side, price, 50)
    assert order.quantity_ahead == 100
    order.update(BookEvent("CANCEL", book_side, price, 40), 0)
    order.update(BookEvent("TRADE", book_side, price, 60), 1)
    assert order.quantity_ahead == order.filled_quantity == 0
    order.update(BookEvent("ADD", book_side, price, 100), 2)
    order.update(BookEvent("TRADE", book_side, price, 20), 3)
    assert order.status == "PARTIAL" and order.remaining_quantity == 30
    order.update(BookEvent("TRADE", book_side, price, 100), 4)
    assert order.status == "FILLED" and order.filled_quantity == 50
    assert order.traded_ahead == 60 and order.cancelled_ahead == 40
    order.update(BookEvent("TRADE", book_side, price, 100), 5)
    assert len(order.fills) == 2


def test_conservative_cancellation_and_cancel_lifecycle():
    order = PassiveOrder("BUY", 5000, 10, 100, False)
    order.update(BookEvent("CANCEL", "BID", 5000, 100), 0)
    order.update(BookEvent("TRADE", "ASK", 5000, 100), 1)
    assert order.quantity_ahead == 100
    order.cancel()
    order.update(BookEvent("TRADE", "BID", 5000, 200), 2)
    assert order.status == "CANCELLED" and order.filled_quantity == 0
    with pytest.raises(ValueError):
        PassiveOrder.join(OrderBook({5000: 1}, {5004: 1}), "BUY", 5004, 10)
