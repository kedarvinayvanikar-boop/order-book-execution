"""Transactional SQLite storage for independently reproducible experiment runs."""

import json
import sqlite3
from importlib.resources import files

import pandas as pd

from .events import BookEvent


def connect(path=":memory:"):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(files("lob").joinpath("schema.sql").read_text())
    return connection


def _insert_frame(connection, table, frame, experiment_id):
    if frame.empty:
        return
    columns = [
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table})")
        if row[1] not in ("experiment_id", "fill_id")
    ]
    data = (
        frame.reindex(columns=columns)
        .astype(object)
        .where(pd.notna(frame.reindex(columns=columns)), None)
    )
    placeholders = ",".join("?" for _ in range(len(columns) + 1))
    connection.executemany(
        f"INSERT INTO {table} (experiment_id,{','.join(columns)}) VALUES ({placeholders})",
        [(experiment_id, *row) for row in data.itertuples(index=False, name=None)],
    )


def save_experiment(connection, config, initial, events, states, executions, fills):
    """Persist a whole run atomically; event IDs are zero-based within a run."""
    with connection:
        experiment_id = connection.execute(
            "INSERT INTO experiments(config_json,initial_book_json) VALUES (?,?)",
            (json.dumps(config, sort_keys=True), json.dumps(initial.snapshot())),
        ).lastrowid
        connection.executemany(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?)",
            [
                (experiment_id, i, e.timestamp, e.event_type, e.side, e.price, e.quantity)
                for i, e in enumerate(events)
            ],
        )
        _insert_frame(
            connection,
            "book_states",
            states.rename(columns={"event_index": "event_id"}),
            experiment_id,
        )
        _insert_frame(connection, "orders", executions, experiment_id)
        _insert_frame(connection, "executions", executions, experiment_id)
        _insert_frame(connection, "fills", fills, experiment_id)
    return experiment_id


def load_events(connection, experiment_id):
    return [
        BookEvent(*row)
        for row in connection.execute(
            "SELECT event_type,side,price,quantity,timestamp FROM events WHERE experiment_id=? ORDER BY event_id",
            (experiment_id,),
        )
    ]
