import importlib.util

import pytest

from lob import BookEvent, execute_market_order
from lob.native import engine, native_events
from lob.queue import PassiveOrder
from lob.simulation import generate_events, initial_book

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("_lob_cpp") is None,
    reason="C++ bindings not built or build/ not on PYTHONPATH",
)


@pytest.mark.parametrize("seed", [7, 42, 123])
def test_every_event_and_final_execution_parity(seed):
    native = engine()
    python = initial_book()
    cpp = native.OrderBook(python.bids, python.asks)
    events = list(generate_events(3000, seed))
    for event, native_event in zip(events, native_events(events)):
        python.apply(event)
        cpp.apply(native_event)
        assert cpp.bids == python.bids and cpp.asks == python.asks
        assert cpp.best_bid == python.best_bid and cpp.best_ask == python.best_ask
    for side in ("BUY", "SELL"):
        for quantity in (0, 1, 600, 100000):
            python_order = python.copy()
            reference = execute_market_order(python_order, side, quantity)
            native_order = native.OrderBook(cpp.bids, cpp.asks)
            result = native_order.execute(side, quantity)
            assert native_order.bids == python_order.bids
            assert native_order.asks == python_order.asks
            assert result.filled_quantity == reference.filled_quantity
            assert result.remaining_quantity == reference.remaining_quantity
            assert (
                result.average_price == pytest.approx(reference.average_price)
                if reference.average_price is not None
                else result.average_price is None
            )
            assert [(f.price, f.quantity) for f in result.fills] == [
                (f.price, f.quantity) for f in reference.fills
            ]


@pytest.mark.parametrize("side,book_side,price", [("BUY", "BID", 5000), ("SELL", "ASK", 5004)])
@pytest.mark.parametrize("cancel_ahead", [True, False])
def test_queue_parity(side, book_side, price, cancel_ahead):
    python = PassiveOrder(side, price, 50, 100, cancel_ahead)
    cpp = engine().PassiveOrder(side, price, 50, 100, cancel_ahead)
    events = [
        BookEvent("ADD", book_side, price, 100),
        BookEvent("CANCEL", book_side, price, 40),
        BookEvent("TRADE", book_side, price, 60),
        BookEvent("TRADE", book_side, price, 20),
        BookEvent("TRADE", book_side, price, 200),
    ]
    for index, (event, native_event) in enumerate(zip(events, native_events(events))):
        python.update(event, index)
        cpp.update(native_event, index)
        assert (cpp.remaining_quantity, cpp.quantity_ahead, cpp.status) == (
            python.remaining_quantity,
            python.quantity_ahead,
            python.status,
        )
        assert cpp.traded_ahead == python.traded_ahead
        assert cpp.cancelled_ahead == python.cancelled_ahead
        assert [(i, f.price, f.quantity) for i, f in cpp.fills] == [
            (i, f.price, f.quantity) for i, f in python.fills
        ]


@pytest.mark.parametrize(
    "kind,side,price,quantity",
    [
        ("ADD", "BID", 5000, -1),
        ("BAD", "BID", 5000, 1),
        ("ADD", "BAD", 5000, 1),
        ("ADD", "BID", 0, 1),
        ("CANCEL", "BID", 5000, 201),
        ("TRADE", "ASK", 5004, 201),
        ("CANCEL", "BID", 1, 1),
    ],
)
def test_native_rejection_is_atomic(kind, side, price, quantity):
    book = engine().OrderBook({5000: 200}, {5004: 200})
    with pytest.raises(ValueError):
        book.apply(engine().Event(kind, side, price, quantity))
    assert book.bids == {5000: 200} and book.asks == {5004: 200}


def test_native_overflow_and_queue_cancellation():
    native = engine()
    book = native.OrderBook({5000: 2**63 - 1}, {})
    with pytest.raises(ValueError):
        book.apply(native.Event("ADD", "BID", 5000, 1))
    assert book.bids == {5000: 2**63 - 1}
    python, cpp = PassiveOrder("BUY", 5000, 10, 0), native.PassiveOrder("BUY", 5000, 10, 0)
    python.cancel()
    cpp.cancel()
    event = BookEvent("TRADE", "BID", 5000, 20)
    python.update(event, 0)
    cpp.update(native_events([event])[0], 0)
    assert python.status == cpp.status == "CANCELLED"
    assert python.remaining_quantity == cpp.remaining_quantity == 10
