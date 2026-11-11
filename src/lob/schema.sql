PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id INTEGER PRIMARY KEY,
    config_json TEXT NOT NULL,
    initial_book_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    experiment_id INTEGER NOT NULL REFERENCES experiments,
    event_id INTEGER NOT NULL CHECK(event_id >= 0),
    timestamp INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('ADD','CANCEL','TRADE')),
    side TEXT NOT NULL CHECK(side IN ('BID','ASK')),
    price INTEGER NOT NULL CHECK(price > 0),
    quantity INTEGER NOT NULL CHECK(quantity >= 0),
    PRIMARY KEY(experiment_id, event_id)
);
CREATE TABLE IF NOT EXISTS book_states (
    experiment_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    best_bid REAL, best_ask REAL,
    bid_quantity INTEGER NOT NULL CHECK(bid_quantity >= 0),
    ask_quantity INTEGER NOT NULL CHECK(ask_quantity >= 0),
    spread REAL, midpoint REAL, imbalance REAL, microprice REAL,
    PRIMARY KEY(experiment_id,event_id),
    FOREIGN KEY(experiment_id,event_id) REFERENCES events
);
CREATE TABLE IF NOT EXISTS orders (
    experiment_id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    start_event INTEGER NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
    style TEXT NOT NULL CHECK(style IN ('PASSIVE','AGGRESSIVE')),
    limit_price INTEGER CHECK(limit_price > 0),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    quantity_ahead INTEGER NOT NULL CHECK(quantity_ahead >= 0),
    PRIMARY KEY(experiment_id,order_id),
    FOREIGN KEY(experiment_id,start_event) REFERENCES events(experiment_id,event_id)
);
CREATE TABLE IF NOT EXISTS fills (
    fill_id INTEGER PRIMARY KEY,
    experiment_id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    event_index INTEGER NOT NULL,
    price INTEGER NOT NULL CHECK(price > 0),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    FOREIGN KEY(experiment_id,order_id) REFERENCES orders,
    FOREIGN KEY(experiment_id,event_index) REFERENCES events(experiment_id,event_id)
);
CREATE TABLE IF NOT EXISTS executions (
    experiment_id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    filled_quantity INTEGER NOT NULL CHECK(filled_quantity >= 0),
    remaining_quantity INTEGER NOT NULL CHECK(remaining_quantity >= 0),
    average_price REAL, benchmark_midpoint REAL,
    slippage REAL, slippage_bps REAL, spread_cost_percentage REAL,
    price_impact_percentage REAL, implementation_cost REAL,
    events_to_fill INTEGER, adverse_selection_5 REAL,
    PRIMARY KEY(experiment_id,order_id),
    FOREIGN KEY(experiment_id,order_id) REFERENCES orders
);
CREATE INDEX IF NOT EXISTS events_flow ON events(experiment_id,side,event_type);
CREATE INDEX IF NOT EXISTS orders_style ON orders(experiment_id,style,side);
CREATE INDEX IF NOT EXISTS fills_order ON fills(experiment_id,order_id);
