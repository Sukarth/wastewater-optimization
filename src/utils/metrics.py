"""Analytics helpers for evaluating controller performance."""
from __future__ import annotations

from typing import Dict

import pandas as pd


def summarize_run(df: pd.DataFrame) -> Dict[str, float]:
    """Compute key indicators from a simulation log."""
    duration_h = len(df) * 0.25  # 15 min steps
    energy_cost = (df["energy_kwh"] * df["price_eur_kwh"]).sum()
    avg_level = df["level_m"].mean()
    max_level = df["level_m"].max()
    min_level = df["level_m"].min()
    constraint_violations = ((df["level_m"] > 7.5) | (df["level_m"] < 1.0)).sum()
    return {
        "duration_h": duration_h,
        "energy_cost_eur": energy_cost,
        "avg_level_m": avg_level,
        "min_level_m": min_level,
        "max_level_m": max_level,
        "constraint_violations": float(constraint_violations),
    }


def compare_strategies(multi_agent: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """Return a tidy dataframe with metrics for presentation charts."""
    rows = []
    for name, df in [("multi_agent", multi_agent), ("baseline", baseline)]:
        summary = summarize_run(df)
        summary["strategy"] = name
        rows.append(summary)
    return pd.DataFrame(rows).set_index("strategy")
