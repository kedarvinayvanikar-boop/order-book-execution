# Order Book Execution Research

A market simulation and research system for studying **what happens between deciding
to trade and actually getting a trade filled**.

It reconstructs an order book as orders arrive, disappear, and trade, then compares
two ways of executing the same decision: buying or selling immediately, or placing
a limit order and waiting in the queue. The aim is to understand how execution
changes the value of a trading signal.

## Why execution matters

Predicting the direction of a price move is only part of a trading decision. You
also need to know what price you can trade at, how much is available, and whether
someone will trade with your order before the opportunity disappears.

An order book is the collection of resting buy and sell orders at different prices.
The highest buy price is the best bid; the lowest sell price is the best ask. The
gap between them is the spread. Buying immediately means paying an available ask.
Placing a buy order at the bid offers a better price, but puts you behind the
liquidity already waiting there.

That creates the central question of this project:

> When is it worth paying for immediate execution, and when is it worth waiting
> for a better price?

Waiting has a cost too. An order may never fill, may fill only partly, or may fill
just before the market moves against it. A signal that looks useful when measured
against the midpoint between bid and ask can lose its advantage once these effects
are included.

## What the system does

The simulator follows changes to available liquidity across multiple price levels.
At selected points, it compares independent immediate and waiting orders from the
same starting market conditions.

| Immediate execution — market order | Waiting for execution — limit order |
|---|---|
| Takes available liquidity at the best prices | Joins a queue at a specified price |
| Can fill across several price levels | Fills as eligible trade flow reaches it |
| Pays the spread and can pay more for larger sizes | Can obtain a better price, but may remain unfilled |

The experiments measure how much of each order fills, the prices received, how long
full fills take, and how prices move after execution. They also retain unfilled
quantity so that a strategy does not look better merely because its unsuccessful
orders have been left out.

Alongside execution, the research layer examines whether the balance of buying and
selling liquidity, and the prices implied by that balance, contain information
about subsequent midpoint moves.

## A concrete example

Suppose the book has 250 shares offered at $50.04, another 300 at $50.05, and 500
at $50.06. A market order to buy 600 shares cannot buy them all at the displayed
best ask. It takes:

```text
250 shares at $50.04
300 shares at $50.05
 50 shares at $50.06
--------------------
600 shares at an average of about $50.0467
```

A limit order at the bid might buy more cheaply, but it first needs the volume ahead
of it to clear. The simulator makes that trade-off measurable: execution price,
queue delay, partial fills, missed quantity, and movement after a fill.

## What the experiments show so far

A reproducible run with 10,000 synthetic events compared 1,200 orders across both
buy and sell sides and three order sizes. The average fraction of each order filled
was:

| Execution approach | Average quantity filled |
|---|---:|
| Immediate market orders | 99.98% |
| Limit orders, assuming cancellations clear volume ahead | 56.53% |
| Limit orders, without that cancellation benefit | 51.88% |

This illustrates two trade-offs: a better possible price comes with less certainty
of execution, and estimates of passive fills depend on assumptions about queue
position. These are results from a synthetic market, not estimates of live-market
fill rates or evidence of a profitable strategy.

The analysis produces six plots covering order size and execution cost, queue
position and fills, liquidity signals and future price movement, and spread and
price-impact distributions. Detailed results and definitions are in the
[engineering guide](docs/engineering.md#measured-results).

## How it is built

**Python** provides the reference book, execution simulation, and research workflow.
**pandas and NumPy** turn event histories into analytical tables; **matplotlib**
produces the plots. **SQLite** stores events, market states, orders, and fills so
experiments can be queried and revisited.

A **C++17 engine**, connected through pybind11, implements book updates, market
execution, and queue processing. Tests compare its state and fills with Python
before measuring performance. In the measured one-million-event workload, median
replay time was 99.04 ms in Python, 20.06 ms in the C++ core, and 33.15 ms including
binding overhead. These are batch processing times on a small synthetic book.

The repository is organized around those responsibilities:

```text
src/lob/    Python engine, simulation, analytics, and storage
cpp/        C++ engine and Python bindings
tests/      Correctness, research, storage, and cross-language tests
scripts/    Commands to run experiments, analysis, and benchmarks
sql/        Research queries
docs/       Engineering details and measurement assumptions
```

## Try it locally

From the repository root, using Python 3.12 or later:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock -e .

python scripts/run_simulation.py --events 10000 --seed 7 --output results/research
python scripts/analyze_results.py --input results/research
```

Look in `results/research/` for the plots, CSV tables, and `research.sqlite` database.
The seed makes the event stream repeatable. The research workflow runs in Python
without requiring a C++ build.

For C++ build instructions, tests, SQL queries, and benchmarks, see the
[engineering guide](docs/engineering.md). Local validation passed 51 Python tests
with the bindings enabled, one C++ test, and formatting/lint checks.

## Scope and next steps

The current system uses generated order flow rather than historical exchange data.
Its queue model estimates position from aggregate liquidity; it cannot reconstruct
individual exchange orders. Fees, rebates, hidden liquidity, and exchange latency
are not modeled.

The next research step is to replay historical data and calibrate the queue
assumptions, then include fees and latency in the execution comparison. The current
system provides a reproducible way to investigate those questions and check the
mechanics before making claims about real trading outcomes.
