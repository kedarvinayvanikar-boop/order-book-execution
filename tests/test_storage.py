import sqlite3
from pathlib import Path

import pytest

from lob.analysis import execution_experiments, replay_frame
from lob.simulation import generate_events, initial_book
from lob.storage import connect, load_events, save_experiment


def test_transaction_roundtrip_queries_and_foreign_keys():
    events = list(generate_events(100))
    book = initial_book()
    states = replay_frame(book, events)
    executions, fills = execution_experiments(book, events, interval=20)
    with connect() as db:
        for _ in range(2):
            run = save_experiment(db, {"seed": 7}, book, events, states, executions, fills)
            assert load_events(db, run) == events
        assert db.execute("SELECT COUNT(*) FROM book_states").fetchone()[0] == 200
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        queries = Path("sql/analysis_queries.sql").read_text()
        for query in queries.split(";"):
            if query.strip():
                db.execute(query).fetchall()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO fills(experiment_id,order_id,event_index,price,quantity) VALUES(999,1,0,5000,1)"
            )
        db.rollback()
        broken = fills.copy()
        broken.loc[len(broken)] = [99999, 0, 5000, 1]
        with pytest.raises(sqlite3.IntegrityError):
            save_experiment(db, {}, book, events, states, executions, broken)
        assert db.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 2
