"""Deterministic tunnel level↔volume conversions based on BLOM spec."""
from __future__ import annotations

import math

# Level breakpoints (meters)
LEVEL_MIN_A = 0.4
LEVEL_MAX_B = 5.9
LEVEL_MAX_C = 8.6
LEVEL_MAX_D = 14.1

# Precomputed volume checkpoints (cubic meters)
VOLUME_MIN = 350.0
VOLUME_B = 75_975.0
VOLUME_C = 150_225.0
VOLUME_MAX = 225_850.0

# Helper coefficients derived from the engineering formulas
_B_QUADRATIC_COEFF = 2_500.0  # 2500 * (level_delta^2)
_C_LINEAR_COEFF = 27_500.0    # 5 * 5_500
_D_QUADRATIC_COEFF = 2_500.0  # Same as B, with inverted parabola


def tunnel_volume_from_level(level_m: float) -> float:
    """Return tunnel volume (m³) for a given level (m) per HSY spec."""
    level = float(level_m)
    if level < LEVEL_MIN_A:
        return VOLUME_MIN
    if level < LEVEL_MAX_B:
        delta = level - LEVEL_MIN_A
        return VOLUME_MIN + _B_QUADRATIC_COEFF * (delta ** 2)
    if level < LEVEL_MAX_C:
        delta = level - LEVEL_MAX_B
        return VOLUME_B + _C_LINEAR_COEFF * delta
    if level <= LEVEL_MAX_D:
        delta = LEVEL_MAX_D - level
        return VOLUME_MAX - _D_QUADRATIC_COEFF * (delta ** 2)
    return VOLUME_MAX


def tunnel_level_from_volume(volume_m3: float) -> float:
    """Inverse of ``tunnel_volume_from_level`` with analytical formulas."""
    volume = float(volume_m3)
    if volume <= VOLUME_MIN:
        return LEVEL_MIN_A
    if volume <= VOLUME_B:
        delta = math.sqrt(max(volume - VOLUME_MIN, 0.0) / _B_QUADRATIC_COEFF)
        return LEVEL_MIN_A + delta
    if volume <= VOLUME_C:
        delta = (volume - VOLUME_B) / _C_LINEAR_COEFF
        return LEVEL_MAX_B + delta
    if volume <= VOLUME_MAX:
        delta = math.sqrt(max(VOLUME_MAX - volume, 0.0) / _D_QUADRATIC_COEFF)
        return LEVEL_MAX_D - delta
    return LEVEL_MAX_D


def clamp_level_to_bounds(level_m: float) -> float:
    """Utility to clamp a level to the physical bounds of the tunnel."""
    return float(min(max(level_m, LEVEL_MIN_A), LEVEL_MAX_D))
