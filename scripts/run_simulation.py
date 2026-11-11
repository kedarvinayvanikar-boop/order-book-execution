"""Generate synthetic flow, execution experiments, and a transactional research store."""

import argparse
import json
from pathlib import Path

from lob.analysis import execution_experiments, execution_summary, replay_frame
from lob.simulation import generate_events, initial_book
from lob.storage import connect, save_experiment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--interval", type=int, default=100)
    parser.add_argument("--window", type=int, default=100)
    parser.add_argument("--conservative-cancels", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    events = list(generate_events(args.events, args.seed))
    initial = initial_book()
    states = replay_frame(initial, events)
    executions, fills = execution_experiments(
        initial,
        events,
        interval=args.interval,
        window=args.window,
        cancellations_ahead=not args.conservative_cancels,
    )
    config = {**vars(args), "output": str(args.output), "data_source": "synthetic"}
    with connect(args.output / "research.sqlite") as db:
        experiment_id = save_experiment(db, config, initial, events, states, executions, fills)
    states.to_csv(args.output / "states.csv", index=False)
    executions.to_csv(args.output / "executions.csv", index=False)
    fills.to_csv(args.output / "fills.csv", index=False)
    execution_summary(executions).to_csv(args.output / "execution_summary.csv")
    (args.output / "config.json").write_text(
        json.dumps({**config, "experiment_id": experiment_id}, indent=2) + "\n"
    )
    print(
        f"Synthetic run {experiment_id}: {len(events)} events, {len(executions)} counterfactual orders"
    )
    print(
        executions.groupby("style")[["fill_rate", "slippage_bps", "implementation_cost"]]
        .mean()
        .to_string()
    )


if __name__ == "__main__":
    main()
