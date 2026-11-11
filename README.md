# Order Book Execution Research

An event-driven order book and execution research system with a Python reference
engine, a C++17 processing core, and a SQLite research store. It studies how spread,
queue position, uncertain fills, and adverse selection separate a price signal
from an executable outcome.

## Architecture

```text
Seeded synthetic ADD / CANCEL / TRADE stream
                    |
             Python book <---- parity ----> C++ book (pybind11)
                    |                         |
          market state / shadow queues / market-order fills
                    |
        execution costs / markouts / SQLite
                    |
           pandas studies / CSV / matplotlib
```

- `src/lob/book.py`, `events.py`: validated multi-level updates, dictionary input
  adapter, and independent history snapshots.
- `execution.py`, `metrics.py`: BUY/SELL book walking, partial fills, VWAP,
  spread/midpoint/imbalance/microprice, signed costs, and adverse selection.
- `queue.py`: passive shadow orders, queue depletion, partial/full fills,
  cancellation, and selectable cancellation attribution.
- `simulation.py`, `analysis.py`: seeded valid flow, event/state DataFrames,
  forward moves/returns, conditional signal studies, and execution comparisons.
- `storage.py`, `schema.sql`: packaged SQLite schema and atomic experiment storage.
- `cpp/`: ordered-map book, market fills, passive queue, bindings, and native tests.
- `tests/`: pytest validation, research/storage integration, and cross-language parity.
- `scripts/`: simulation, analysis, and batch benchmarks.
- `sql/analysis_queries.sql`: size/queue buckets, execution costs, spread by event
  type, imbalance versus future direction, and worst execution outcomes.
- `.github/workflows/tests.yml`: Python lint/tests, CMake/CTest, and research smoke runs.

The ignored local `exercises/` directory is the original behavioral reference.
Production code, builds, and tests do not import it. Its contents remain untouched.

## Install and verify

Python 3.12+, a C++17 compiler, and CMake 3.20+ are required for the full workflow.
The Python engine can run without building C++.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock -e .
# Alternatively: python -m pip install -e '.[dev]'

python -m pytest -q
ruff check src tests scripts
ruff format --check src tests scripts

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DPython_EXECUTABLE="$VIRTUAL_ENV/bin/python"
cmake --build build --parallel
ctest --test-dir build --output-on-failure
PYTHONPATH=build:src python -m pytest -q
```

Before a native build, parity tests explicitly skip. The last command must run with
bindings present to validate both implementations. C++ alone can be built using
`-DLOB_PYTHON=OFF`, without pybind11 or a Python development installation.

The lock file records the tested dependency versions. `pyproject.toml` also permits
newer compatible installations; rerun correctness checks when upgrading.

## Run research

```sh
python scripts/run_simulation.py --events 10000 --seed 7 --output results/research
python scripts/analyze_results.py --input results/research
python scripts/run_simulation.py --events 10000 --seed 7 \
  --conservative-cancels --output results/conservative
sqlite3 results/research/research.sqlite < sql/analysis_queries.sql
PYTHONPATH=build:src python scripts/benchmark_engines.py
```

Simulation initializes SQLite automatically. Each run appends a separate experiment
with its configuration, initial book, events, post-event states, orders, fills, and
execution summaries. Composite keys isolate runs; foreign keys are enabled and
inserts are transactional. The CSVs and configuration JSON describe the latest run
in that output directory. Generated files, databases, plots, binaries, and caches
are ignored by Git.

Analysis writes conditional signal tables, execution summaries, and six plots:
imbalance, microprice displacement, slippage versus size, passive fill fraction
versus quantity ahead, implementation cost by style, and spread/impact distributions.

A direct engine call uses **integer cent ticks**:

```python
from lob import BookEvent, OrderBook, execute_market_order
from lob.metrics import book_metrics

book = OrderBook({5000: 750}, {5004: 250, 5005: 300, 5006: 500})
book.apply(BookEvent("ADD", "BID", 4999, 100))
result = execute_market_order(book, "BUY", 600)
assert [fill.quantity for fill in result.fills] == [250, 300, 50]
print(result.average_price, book_metrics(book))
```

`OrderBook.from_dict` and `BookEvent.from_dict` accept the original capitalized
keys and currency prices. Off-tick, nonfinite, nonpositive prices and invalid
quantities are rejected. Zero quantity is a no-op on existing levels; zero-size
ADD does not create a level. Missing-level removals fail even at zero quantity.
Reconstruction permits locked/crossed snapshots; ADD does not automatically match
liquidity. The instrument tick size is fixed at 0.01.
Events name the **resting side** (`BID`/`ASK`); orders name the **aggressor side**
(`BUY`/`SELL`). Fixed-price TRADE is not a multi-level market order.

## Measurement conventions

Fill prices and book keys use signed 64-bit integer cent ticks; quantities are
nonnegative integers in the same range. Reported average prices, quotes, spread,
and absolute costs use currency units. Empty quotes and undefined metrics use
`None`/SQL NULL/pandas missing values. Level maps are owned by the engine; use
`apply`/`execute_market_order` to change them and `snapshot` for independent data.

Positive signed slippage is a cost:

- BUY: average execution price minus arrival midpoint.
- SELL: arrival midpoint minus average execution price.
- Basis points: signed cost / arrival midpoint × 10,000.
- Spread cost percentage: half the arrival spread / midpoint × 100.
- Price impact percentage: side-signed *mechanical* midpoint change after a market
  order / arrival midpoint × 100. It is undefined if an entire quote side disappears.
- Adverse-selection loss: negative side-signed midpoint movement after a fill,
  reported at 1/5/10/50-event horizons. Positive values mean adverse movement.
  Aggressive fills occur before the starting event; passive fills occur after
  their matching event. Only observed two-sided quote pairs enter markouts, and
  eligible filled quantity is reported at each horizon.

Event frames contain post-event state. Forward returns are fractional returns;
forward moves are absolute currency changes. Signal studies include unchanged
midpoints in the probability denominator and exclude missing future observations.
No tail observations are filled with zero returns.

Execution comparisons submit independent BUY and SELL orders of 50, 200, and 600
shares every 100 events, observe 100 events of flow, and retain partial fills.
Summaries report both mean quantity fill fraction and
full-fill probability; each trial records its actual observation window. Tail
windows and markouts can be right-censored.
`events_to_fill` is zero for immediate full market fills and missing for incomplete
orders. Average slippage is conditional on execution. Implementation cost uses
filled notional plus remaining quantity marked to the terminal midpoint, relative
to arrival midpoint, per requested share. This makes the unfilled opportunity cost
visible without silently dropping unfilled orders. It does not assume a terminal
market fill at that midpoint. Price improvement compares each passive fill price
with its aggressive counterfactual VWAP.

## Queue assumptions and research limits

Each passive order is an independent counterfactual; orders from different trials
never compete with one another. Initial quantity ahead equals displayed same-side
depth at the limit. Subsequent ADD flow joins behind the shadow order. Eligible
TRADE volume removes quantity ahead before filling the order. Flow at other prices
and on the opposite side does not affect its queue. Filled/cancelled orders no
longer receive updates. Marketable limit prices are rejected when joining a book.

By default CANCEL volume is assumed to remove quantity ahead first. The conservative
mode never credits cancellations ahead. These are alternative assumptions about
unobserved position, not calibrated estimates. Shadow fills do not alter the replayed
book or other trials. Same-price flow only and no order IDs mean this is an aggregate
Level-2 queue approximation, **not Level-3 FIFO reconstruction**. There are no fees,
rebates, exchange latency, hidden orders, matching priorities, or permanent impact.

Synthetic flow is a bounded grid with random replenishment and depletion. It is
neither exchange data nor an empirically calibrated market model. Overlapping trial
windows are dependent. Conditional buckets describe this generator; they cannot
establish causal effects, significance, a real fill probability, or profitability.
Future work could add licensed replay data, calibrated cancellation attribution,
and explicit fees/latency before drawing trading conclusions.

## Measured results

Local validation on November 11, 2026: **51 pytest cases passed** with bindings,
**1 CTest passed**, and Ruff checks passed. All four original reference scripts
passed before migration, with bytecode writing disabled.

The seed-7, 10,000-event run produced 1,200 independent orders:

| Execution style | Mean quantity fill fraction | Mean filled-order slippage (bps) | Mean implementation cost/share |
|---|---:|---:|---:|
| Aggressive | 0.999797 | 5.109625 | 0.025550 |
| Passive, cancellations ahead | 0.565297 | -2.585914 | -0.007131 |
| Passive, conservative cancellations | 0.518767 | -2.571961 | -0.006478 |

A negative synthetic cost reflects spread capture and this generator's behavior;
it is not a finding about live execution profitability.

Benchmarks on macOS 26.6.2 arm64, Python 3.12.14, Apple Clang 21.0.0,
CMake Release (`-O3 -DNDEBUG`, C++17), seed 7:

| Events | Python median (ms) | C++ core median (ms) | C++ including binding (ms) | Core speedup |
|---:|---:|---:|---:|---:|
| 10,000 | 0.964 | 0.129 | 0.255 | 7.45× |
| 100,000 | 9.789 | 2.032 | 3.285 | 4.82× |
| 1,000,000 | 99.036 | 20.061 | 33.148 | 4.94× |

One whole-stream warmup/parity replay precedes five timed repetitions. Medians are
whole-batch runtimes. Event generation and conversion to bound Event objects are
excluded from both timings. The C++ core also excludes vector conversion, book
copy, and result binding; the binding-inclusive column includes those costs.
Raw samples, machine/compiler details, throughput, and methodology are written to
`results/benchmarks.json`. The benchmark checks final state parity before timing;
the test suite separately checks every event, fills, VWAP, and queue transitions.
There are no message-latency percentile or production HFT performance claims.

Python dictionaries make direct level updates cheap but require scanning for best
prices and sorting for book walks. C++ `std::map` provides O(log L) updates and
constant-time endpoint access, at the cost of node allocations and pointer traversal.
The bounded synthetic workload has few levels: these numbers do not describe a
deep exchange book. No alternative container has been shown to outperform the map.
