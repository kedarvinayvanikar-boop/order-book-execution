"""Write conditional studies and restrained plots from a simulator output directory."""

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/lob-matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lob.analysis import execution_summary, signal_study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("results"))
    args = parser.parse_args()
    states = pd.read_csv(args.input / "states.csv")
    executions = pd.read_csv(args.input / "executions.csv")
    for signal in ("imbalance", "microprice_minus_midpoint"):
        study = signal_study(states, signal)
        study.to_csv(args.input / f"{signal}_study.csv")
        ax = study.probability_up.plot.bar(color="#36688d", rot=25, figsize=(8, 4))
        ax.set(
            ylabel="P(next midpoint is higher)",
            xlabel=signal,
            title="Synthetic flow; flat next moves included",
        )
        plt.tight_layout()
        plt.savefig(args.input / f"{signal}.png", dpi=160)
        plt.close()
    execution_summary(executions).to_csv(args.input / "execution_summary.csv")
    figures = [
        (
            executions[executions.style == "AGGRESSIVE"].groupby("quantity").slippage_bps.mean(),
            "slippage_by_size",
            "Requested quantity",
            "Mean slippage (bps)",
        ),
        (
            executions[executions.style == "PASSIVE"]
            .assign(
                queue_bucket=lambda x: pd.cut(x.quantity_ahead, [-1, 100, 300, 1000, float("inf")])
            )
            .groupby("queue_bucket", observed=True)
            .fill_rate.mean(),
            "passive_queue",
            "Quantity ahead",
            "Mean quantity fill fraction",
        ),
        (
            executions.groupby("style").implementation_cost.mean(),
            "execution_cost",
            "Execution style",
            "Cost per requested share (currency)",
        ),
    ]
    for series, name, xlabel, ylabel in figures:
        ax = series.plot.bar(color="#36688d", rot=20, figsize=(7, 4))
        ax.set(xlabel=xlabel, ylabel=ylabel, title="Synthetic counterfactual executions")
        plt.tight_layout()
        plt.savefig(args.input / f"{name}.png", dpi=160)
        plt.close()
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    states.spread.dropna().hist(ax=axes[0], bins=20, color="#36688d")
    axes[0].set(xlabel="Spread (currency)", ylabel="Post-event observations")
    executions.price_impact_percentage.dropna().hist(ax=axes[1], bins=20, color="#36688d")
    axes[1].set(xlabel="Mechanical midpoint impact (%)", ylabel="Aggressive orders")
    fig.tight_layout()
    fig.savefig(args.input / "spread_and_impact.png", dpi=160)
    plt.close(fig)
    print(f"Wrote conditional studies and six plots to {args.input}")


if __name__ == "__main__":
    main()
