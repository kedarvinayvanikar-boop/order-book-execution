"""Event-aligned research frames and independent execution counterfactuals."""

from dataclasses import asdict

import numpy as np
import pandas as pd

from .events import integer
from .execution import analyze_market_order
from .metrics import adverse_selection, book_metrics, slippage
from .queue import PassiveOrder


def replay_frame(initial, events, horizons=(1, 5, 10, 50)):
    """Rows describe post-event state; forward changes are absolute currency moves."""
    book = initial.copy()
    rows = []
    for index, event in enumerate(events):
        book.apply(event)
        row = asdict(event)
        row.update(event_index=index, event_price=event.price / 100, **book_metrics(book))
        rows.append(row)
    columns = [
        "event_type",
        "side",
        "price",
        "quantity",
        "timestamp",
        "event_index",
        "event_price",
        "best_bid",
        "best_ask",
        "bid_quantity",
        "ask_quantity",
        "spread",
        "midpoint",
        "imbalance",
        "microprice",
    ]
    frame = pd.DataFrame(rows, columns=columns)
    frame["microprice_minus_midpoint"] = frame.microprice - frame.midpoint
    for horizon in horizons:
        integer(horizon, "horizon", 1)
        frame[f"midpoint_move_forward_{horizon}"] = frame.midpoint.shift(-horizon) - frame.midpoint
        frame[f"midpoint_return_forward_{horizon}"] = (
            frame.midpoint.shift(-horizon) / frame.midpoint - 1
        )
    return frame


def signal_study(frame, signal="imbalance", horizon=1):
    """Bucket contemporaneous signals without treating censored future moves as flat."""
    column = f"midpoint_move_forward_{horizon}"
    data = frame[[signal, column]].dropna().copy()
    boundaries = (
        [-1.01, -0.6, -0.2, 0.2, 0.6, 1.01]
        if signal == "imbalance"
        else [-np.inf, -0.01, -0.002, 0.002, 0.01, np.inf]
    )
    data["bucket"] = pd.cut(data[signal], boundaries)
    data["up"] = data[column] > 0
    return data.groupby("bucket", observed=False).agg(
        observations=(column, "size"),
        probability_up=("up", "mean"),
        average_move=(column, "mean"),
        volatility=(column, "std"),
    )


def execution_experiments(
    initial,
    events,
    interval=100,
    window=100,
    sizes=(50, 200, 600),
    horizons=(1, 5, 10, 50),
    cancellations_ahead=True,
):
    """Compare independent BUY/SELL orders from identical pre-event states.

    Passive orders are shadows: their fills do not alter future historical flow.
    Unfilled quantity is marked to the terminal midpoint as opportunity cost.
    Missing terminal/future quotes remain undefined rather than becoming zero costs.
    """
    integer(interval, "interval", 1)
    integer(window, "window", 1)
    states, book = [], initial.copy()
    for event in events:
        states.append(book.copy())
        book.apply(event)
    states.append(book.copy())
    rows, fill_rows = [], []
    for start in range(0, len(events), interval):
        end = min(len(events), start + window)
        before = book_metrics(states[start])
        terminal = book_metrics(states[end])["midpoint"]
        for side in ("BUY", "SELL"):
            price = states[start].best_bid if side == "BUY" else states[start].best_ask
            if price is None or before["midpoint"] is None:
                continue
            depth = before["ask_quantity"] if side == "BUY" else before["bid_quantity"]
            for size in sizes:
                integer(size, "order size", 1)
                aggressive, costs = analyze_market_order(states[start].copy(), side, size)
                passive = PassiveOrder.join(states[start], side, price, size, cancellations_ahead)
                for index in range(start, end):
                    passive.update(events[index], index)
                for style in ("AGGRESSIVE", "PASSIVE"):
                    order_id = len(rows) + 1
                    if style == "AGGRESSIVE":
                        filled, remaining, average = (
                            aggressive.filled_quantity,
                            aggressive.remaining_quantity,
                            aggressive.average_price,
                        )
                        fills = [(start, fill) for fill in aggressive.fills]
                        local_costs = costs
                    else:
                        filled, remaining = passive.filled_quantity, passive.remaining_quantity
                        average = price / 100 if filled else None
                        fills = passive.fills
                        local_costs = {"slippage": slippage(side, average, before["midpoint"])}
                        local_costs["slippage_bps"] = (
                            local_costs["slippage"] / before["midpoint"] * 10000 if filled else None
                        )
                    cost = local_costs["slippage"]
                    opportunity = slippage(side, terminal, before["midpoint"])
                    total = (
                        ((cost or 0) * filled + (opportunity or 0) * remaining) / size
                        if (not remaining or opportunity is not None)
                        else None
                    )
                    row = {
                        "order_id": order_id,
                        "start_event": start,
                        "side": side,
                        "style": style,
                        "limit_price": price if style == "PASSIVE" else None,
                        "quantity": size,
                        "filled_quantity": filled,
                        "remaining_quantity": remaining,
                        "average_price": average,
                        "benchmark_midpoint": before["midpoint"],
                        "quantity_ahead": states[start].bids.get(price, 0)
                        if side == "BUY"
                        else states[start].asks.get(price, 0),
                        "fill_rate": filled / size,
                        "events_to_fill": (
                            (0 if style == "AGGRESSIVE" else fills[-1][0] - start + 1)
                            if remaining == 0 and fills
                            else None
                        ),
                        "spread": before["spread"],
                        "imbalance": before["imbalance"],
                        "displayed_depth": depth,
                        "size_to_depth": size / depth if depth else None,
                        "implementation_cost": total,
                    }
                    row.update(local_costs)
                    row["price_improvement"] = slippage(side, aggressive.average_price, average)
                    offset = 0 if style == "AGGRESSIVE" else 1
                    for horizon in horizons:
                        integer(horizon, "horizon", 1)
                        eligible = [
                            (idx, fill)
                            for idx, fill in fills
                            if idx + offset + horizon < len(states)
                            and book_metrics(states[idx + offset])["midpoint"] is not None
                            and book_metrics(states[idx + offset + horizon])["midpoint"] is not None
                        ]
                        volume = sum(fill.quantity for _, fill in eligible)
                        row[f"adverse_selection_{horizon}"] = (
                            sum(
                                adverse_selection(
                                    side,
                                    book_metrics(states[idx + offset])["midpoint"],
                                    book_metrics(states[idx + offset + horizon])["midpoint"],
                                )
                                * fill.quantity
                                for idx, fill in eligible
                            )
                            / volume
                            if volume
                            else None
                        )
                        row[f"markout_quantity_{horizon}"] = volume
                    rows.append(row)
                    for idx, fill in fills:
                        fill_rows.append(
                            {
                                "order_id": order_id,
                                "event_index": idx,
                                "price": fill.price,
                                "quantity": fill.quantity,
                            }
                        )
    return pd.DataFrame(rows), pd.DataFrame(
        fill_rows, columns=["order_id", "event_index", "price", "quantity"]
    )


def execution_summary(executions):
    data = executions.copy()
    data["queue_bucket"] = pd.cut(data.quantity_ahead, [-1, 100, 300, 1000, np.inf])
    data["size_bucket"] = pd.cut(data.size_to_depth, [0, 0.5, 1, 2, np.inf], include_lowest=True)
    return data.groupby(["style", "side", "queue_bucket", "size_bucket"], observed=True).agg(
        orders=("order_id", "size"),
        fill_rate=("fill_rate", "mean"),
        slippage_bps=("slippage_bps", "mean"),
        cost=("implementation_cost", "mean"),
        events_to_fill=("events_to_fill", "mean"),
        adverse_selection=("adverse_selection_5", "mean"),
    )
