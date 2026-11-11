import pytest

from lob import BookEvent, OrderBook
from lob.analysis import execution_experiments, replay_frame, signal_study
from lob.simulation import generate_events, initial_book


def test_seeded_replay_and_censored_forward_values():
    events = list(generate_events(500, 42))
    assert events == list(generate_events(500, 42))
    frame = replay_frame(initial_book(), events)
    assert len(frame) == 500
    assert frame.midpoint_return_forward_5.iloc[-5:].isna().all()
    assert frame.midpoint_move_forward_1.iloc[0] == pytest.approx(
        frame.midpoint.iloc[1] - frame.midpoint.iloc[0]
    )
    study = signal_study(frame)
    assert (
        study.observations.sum()
        == frame[["imbalance", "midpoint_move_forward_1"]].dropna().shape[0]
    )
    assert len(replay_frame(initial_book(), [])) == 0


def test_passive_vs_aggressive_known_flow():
    book = OrderBook({5000: 100}, {5004: 200})
    events = [
        BookEvent("TRADE", "BID", 5000, 100),
        BookEvent("ADD", "BID", 5000, 100),
        BookEvent("TRADE", "BID", 5000, 50),
    ]
    executions, fills = execution_experiments(book, events, interval=10, window=3, sizes=(50,))
    buy = executions[executions.side == "BUY"].set_index("style")
    assert buy.loc["PASSIVE", "fill_rate"] == 1
    assert buy.loc["PASSIVE", "events_to_fill"] == 3
    assert buy.loc["PASSIVE", "slippage"] == pytest.approx(-0.02)
    assert buy.loc["AGGRESSIVE", "slippage"] == pytest.approx(0.02)
    assert buy.loc["PASSIVE", "price_improvement"] == pytest.approx(0.04)
    assert (
        fills.groupby("order_id")
        .quantity.sum()
        .reindex(executions.order_id, fill_value=0)
        .to_dict()
        == executions.set_index("order_id").filled_quantity.to_dict()
    )
    assert book.bids == {5000: 100}
