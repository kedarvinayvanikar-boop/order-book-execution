"""Warm batch benchmarks with state parity before timing; no per-event latency claims."""

import argparse
import json
import platform
import statistics
import subprocess
import time
from pathlib import Path

from lob.native import engine, native_events
from lob.simulation import generate_events, initial_book


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", type=int, nargs="+", default=[10000, 100000, 1000000])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("results/benchmarks.json"))
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error("at least two repeats required")
    native = engine()
    rows = []
    for count in args.counts:
        events = list(generate_events(count))
        converted = native_events(events)
        initial = initial_book()
        cpp_initial = native.OrderBook(initial.bids, initial.asks)
        reference = initial.copy()
        for event in events:
            reference.apply(event)
        _, result = native.time_replay(cpp_initial, converted)
        assert result.bids == reference.bids and result.asks == reference.asks, (
            "state parity failed"
        )
        python_times, cpp_times, bound_times = [], [], []
        for _ in range(args.repeats):
            book = initial.copy()
            start = time.perf_counter()
            for event in events:
                book.apply(event)
            python_times.append(time.perf_counter() - start)
            start = time.perf_counter()
            elapsed, result = native.time_replay(cpp_initial, converted)
            bound_times.append(time.perf_counter() - start)
            cpp_times.append(elapsed)
        py_median = statistics.median(python_times)
        cpp_median = statistics.median(cpp_times)
        row = {
            "events": count,
            "python_median_seconds": py_median,
            "cpp_kernel_median_seconds": cpp_median,
            "cpp_binding_median_seconds": statistics.median(bound_times),
            "python_events_per_second": count / py_median,
            "cpp_events_per_second": count / cpp_median,
            "kernel_speedup": py_median / cpp_median,
            "python_samples": python_times,
            "cpp_samples": cpp_times,
            "binding_samples": bound_times,
        }
        rows.append(row)
        print(
            f"{count:>9,} events | Python {py_median:.6f}s | C++ kernel {cpp_median:.6f}s | binding {row['cpp_binding_median_seconds']:.6f}s | {row['kernel_speedup']:.2f}x kernel"
        )
    report = {
        "machine": platform.platform(),
        "processor": platform.machine(),
        "python": platform.python_version(),
        "compiler": subprocess.check_output(["c++", "--version"], text=True).splitlines()[0],
        "build": "CMake Release (-O3 -DNDEBUG); C++17",
        "methodology": "Seed 7; one full warmup/parity replay; median of repeated whole batches. Generation/conversion to bound Event objects excluded. Kernel also excludes vector conversion, book copy, and return binding. Binding includes these costs. No per-message percentiles.",
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
