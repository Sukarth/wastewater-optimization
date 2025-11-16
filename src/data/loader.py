"""Utilities for loading and preparing HSY wastewater datasets."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_hsy_timeseries(path: Path | None = None) -> pd.DataFrame:
    """Return the raw HSY operational time series with unified datetime index."""
    csv_path = path or (DATA_DIR / "Hackathon_HSY_data.xlsx")
    df = pd.read_excel(csv_path)
    df = df.rename(columns={df.columns[0]: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.loc[df["timestamp"].notna()].copy()
    numeric_cols = df.columns.drop("timestamp")
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    df = df.set_index("timestamp").sort_index()
    df = df.asfreq("15min")
    df = df.interpolate(limit_direction="both")
    return df


def load_volume_curve(path: Path | None = None) -> pd.DataFrame:
    """Load level↔volume calibration table for the tunnel."""
    csv_path = path or (DATA_DIR / "Volume of tunnel vs level Blominmäki.xlsx")
    df = pd.read_excel(csv_path)
    df = df.rename(
        columns={
            "Level L1 m": "level_m",
            "Volume V m³": "volume_m3",
            "Formula type": "formula_type",
        }
    )
    return df


@dataclass(frozen=True)
class PumpBounds:
    """Container for empirical pump flow bounds."""

    min_flow_m3_per_h: float
    max_flow_m3_per_h: float


def derive_pump_bounds(df: pd.DataFrame, column: str) -> PumpBounds:
    """Derive conservative pump bounds from historical percentiles."""
    flow = df[column].dropna()
    lower = float(flow.quantile(0.02))
    upper = float(flow.quantile(0.98))
    return PumpBounds(min_flow_m3_per_h=max(lower, 0.0), max_flow_m3_per_h=max(upper, 0.0))


def compute_baseline_energy(df: pd.DataFrame) -> pd.Series:
    """Approximate historical energy usage cost using efficiency columns."""
    price = df["Electricity price 2: normal"].fillna(method="ffill")
    energy_terms = []
    for pump_col, eff_col in zip(
        [
            "Pump flow 1.1",
            "Pump flow 1.2",
            "Pump flow 1.3",
            "Pump flow 1.4",
            "Pump flow 2.1",
            "Pump flow 2.2",
            "Pump flow 2.3",
            "Pump flow 2.4",
        ],
        [
            "Pump efficiency 1.1",
            "Pump efficiency 1.2",
            "Pump efficiency 1.3",
            "Pump efficiency 1.4",
            "Pump efficiency 2.1",
            "Pump efficiency 2.2",
            "Pump efficiency 2.3",
            "Pump efficiency 2.4",
        ],
    ):
        if pump_col not in df.columns or eff_col not in df.columns:
            continue
        flow = df[pump_col].fillna(0.0)
        efficiency = df[eff_col].replace(0, pd.NA).fillna(method="ffill").fillna(method="bfill")
        energy_terms.append(flow / efficiency)
    total_specific_energy = sum(energy_terms)
    return total_specific_energy * price


def prepare_training_windows(df: pd.DataFrame, horizon: int = 8) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Create feature/target windows for forecasting experiments."""
    features = df[["Inflow to tunnel F1", "Electricity price 2: normal"]].copy()
    targets = features.shift(-horizon)
    features = features.dropna()
    targets = targets.loc[features.index]
    return features, targets
