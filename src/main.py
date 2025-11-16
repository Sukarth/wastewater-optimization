"""Entry point for running baseline vs multi-agent simulations."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.agents.coordinator import CoordinatorConfig, MultiAgentCoordinator
from src.utils.metrics import compare_strategies


def run_day(start: str = "2024-11-15 00:00", steps: int = 96) -> None:
    coordinator = MultiAgentCoordinator(CoordinatorConfig())
    multi_agent = coordinator.run_multi_agent(steps=steps, start=pd.Timestamp(start))
    baseline = coordinator.run_baseline(steps=steps, start=pd.Timestamp(start))
    comparison = compare_strategies(multi_agent, baseline)
    event_log = coordinator.get_event_log()

    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    multi_agent.to_csv(results_dir / "multi_agent_log.csv")
    baseline.to_csv(results_dir / "baseline_log.csv")
    comparison.to_csv(results_dir / "summary.csv")
    if not event_log.empty:
        event_log.to_csv(results_dir / "agent_log.csv", index=False)
    print("Saved results into", results_dir)


if __name__ == "__main__":
    run_day()
