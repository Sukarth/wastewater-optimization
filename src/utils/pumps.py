"""Pump helper functions derived from Grundfos reference curves."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import numpy as np

SMALL_PUMPS_PREFIX = "Pump flow 1."
LARGE_PUMPS_PREFIX = "Pump flow 2."

NOMINAL_FLOWS_M3_PER_H = {
    "small": 1_670.0,
    "large": 3_330.0,
}

# (ratio to nominal, efficiency)
EFFICIENCY_POINTS: Dict[str, Tuple[Tuple[float, float], ...]] = {
    "small": (
        (0.80, 0.79),
        (0.90, 0.805),
        (1.00, 0.816),
        (1.10, 0.805),
        (1.20, 0.780),
    ),
    "large": (
        (0.75, 0.81),
        (0.85, 0.835),
        (0.95, 0.845),
        (1.05, 0.848),
        (1.15, 0.835),
        (1.30, 0.800),
    ),
}

# (ratio to nominal, drive frequency Hz)
FREQUENCY_POINTS: Dict[str, Tuple[Tuple[float, float], ...]] = {
    "small": (
        (0.70, 40.0),
        (0.80, 45.0),
        (0.90, 47.8),
        (1.00, 50.0),
        (1.10, 50.0),
    ),
    "large": (
        (0.70, 40.0),
        (0.80, 45.0),
        (0.90, 47.8),
        (1.00, 50.0),
        (1.10, 50.0),
        (1.20, 50.0),
    ),
}


def _pump_group(pump_name: str) -> str:
    if pump_name.startswith(SMALL_PUMPS_PREFIX):
        return "small"
    if pump_name.startswith(LARGE_PUMPS_PREFIX):
        return "large"
    return "small"


def nominal_flow_m3_per_h(pump_name: str) -> float:
    """Return the nominal m³/h for the given pump."""
    return NOMINAL_FLOWS_M3_PER_H[_pump_group(pump_name)]


def pump_efficiency(pump_name: str, flow_m3_per_h: float) -> float:
    """Interpolate Grundfos η curve for a pump at the requested flow."""
    group = _pump_group(pump_name)
    points = EFFICIENCY_POINTS[group]
    ratios, effs = zip(*points)
    nominal = nominal_flow_m3_per_h(pump_name)
    if nominal <= 0:
        return 0.80
    ratio = flow_m3_per_h / nominal
    ratio = float(np.clip(ratio, ratios[0], ratios[-1]))
    efficiency = float(np.interp(ratio, ratios, effs))
    return max(efficiency, 0.70)


def estimated_frequency_hz(pump_name: str, flow_m3_per_h: float) -> float:
    """Map flow to drive frequency for monitoring/constraints."""
    group = _pump_group(pump_name)
    points = FREQUENCY_POINTS[group]
    ratios, freqs = zip(*points)
    nominal = nominal_flow_m3_per_h(pump_name)
    if nominal <= 0:
        return 50.0
    ratio = flow_m3_per_h / nominal
    ratio = float(np.clip(ratio, ratios[0], ratios[-1]))
    return float(np.interp(ratio, ratios, freqs))


@dataclass(frozen=True)
class PumpAllocation:
    """Convenience structure for reporting pump usage statistics."""

    pump: str
    total_runtime_steps: int
    cumulative_flow_m3_per_h: float


def order_pumps_by_size(pumps: Iterable[str]) -> Tuple[str, ...]:
    """Return pump names sorted from smallest to largest capacity."""
    classified = []
    for pump in pumps:
        group = _pump_group(pump)
        nominal = NOMINAL_FLOWS_M3_PER_H[group]
        classified.append((nominal, pump))
    classified.sort()
    return tuple(p for _, p in classified)
