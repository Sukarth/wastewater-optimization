"""Digital twin style simulation for the HSY wastewater tunnel."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd

from src.data.loader import load_hsy_timeseries
from src.utils.pumps import pump_efficiency
from src.utils.volume import tunnel_level_from_volume, tunnel_volume_from_level


@dataclass
class EnvConfig:
    timestep_minutes: int = 15
    level_column: str = "Water level in tunnel L2"  # CONFIRMED: This column IS L1 (tunnel suction side) per HSY Discord 11/14
    inflow_column: str = "Inflow to tunnel F1"
    price_column: str = "Electricity price 2: normal"  # Values in cents/kWh, converted to EUR in code
    min_tunnel_level_m: float = 0.5  # Safe level per HSY (0 is where dry-run preventer kicks in)
    max_tunnel_level_m: float = 8.0
    
    # Physical constants from challenge documents
    L2_WWTP_level_m: float = 30.0  # Discharge elevation at WWTP (constant)
    water_density_kg_per_m3: float = 1000.0  # Water density
    gravity_m_per_s2: float = 9.81  # Gravitational acceleration
    
    # Pump specifications from Grundfos curves
    # Small pumps (1.1-1.4): 250 kW, η=81.6%, Q≈1670 m³/h at optimal point
    # Large pumps (2.1-2.4): 400 kW, η=84.8%, Q≈3330 m³/h at optimal point
    pump_flow_columns: Tuple[str, ...] = (
        "Pump flow 1.1",
        "Pump flow 1.2",
        "Pump flow 1.3",
        "Pump flow 1.4",
        "Pump flow 2.1",
        "Pump flow 2.2",
        "Pump flow 2.3",
        "Pump flow 2.4",
    )
    
    # Real pump efficiencies from Grundfos pump curves (as decimals, not percentages)
    pump_efficiencies: Dict[str, float] = field(default_factory=lambda: {
        "Pump flow 1.1": 0.816,  # Small pump: 81.6% efficiency
        "Pump flow 1.2": 0.816,
        "Pump flow 1.3": 0.816,
        "Pump flow 1.4": 0.816,
        "Pump flow 2.1": 0.848,  # Large pump: 84.8% efficiency
        "Pump flow 2.2": 0.848,
        "Pump flow 2.3": 0.848,
        "Pump flow 2.4": 0.848,
    })
    
    # Pump power consumption columns (kW) - what Excel calls "efficiency" is actually power
    pump_power_columns: Tuple[str, ...] = (
        "Pump efficiency 1.1",  # Actually power in kW
        "Pump efficiency 1.2",
        "Pump efficiency 1.3",
        "Pump efficiency 1.4",
        "Pump efficiency 2.1",
        "Pump efficiency 2.2",
        "Pump efficiency 2.3",
        "Pump efficiency 2.4",
    )
    
    # Pump frequency columns (Hz) - must be ≥47.8 Hz per HSY Discord (11/14/25)
    pump_frequency_columns: Tuple[str, ...] = (
        "Pump frequency 1.1",
        "Pump frequency 1.2",
        "Pump frequency 1.3",
        "Pump frequency 1.4",
        "Pump frequency 2.1",
        "Pump frequency 2.2",
        "Pump frequency 2.3",
        "Pump frequency 2.4",
    )

    # Rated capacities at ~50 Hz (m³/h)
    pump_capacity_m3_per_h: Dict[str, float] = field(default_factory=lambda: {
        # Small pumps ≈ 464 l/s (≈1670 m³/h)
        "Pump flow 1.1": 1700.0,
        "Pump flow 1.2": 1700.0,
        "Pump flow 1.3": 1700.0,
        "Pump flow 1.4": 1700.0,
        # Large pumps ≈ 925 l/s (≈3330 m³/h)
        "Pump flow 2.1": 3350.0,
        "Pump flow 2.2": 3350.0,
        "Pump flow 2.3": 3350.0,
        "Pump flow 2.4": 3350.0,
    })

    # Minimum flow corresponding to ≥47.8 Hz operation (HSY requirement)
    # These values ensure pumps operate at or above minimum frequency
    pump_min_full_speed_m3_per_h: Dict[str, float] = field(default_factory=lambda: {
        "Pump flow 1.1": 1400.0,  # ~47.8 Hz for small pumps
        "Pump flow 1.2": 1400.0,
        "Pump flow 1.3": 1400.0,
        "Pump flow 1.4": 1400.0,
        "Pump flow 2.1": 3000.0,  # ~47.8 Hz for large pumps
        "Pump flow 2.2": 3000.0,
        "Pump flow 2.3": 3000.0,
        "Pump flow 2.4": 3000.0,
    })


@dataclass
class SimulationState:
    timestamp: pd.Timestamp
    tunnel_volume_m3: float
    tunnel_level_m: float
    price_eur_per_kwh: float
    inflow_m3_per_h: float
    pump_flows_m3_per_h: Dict[str, float]


class DigitalTwinEnv:
    """Replay-based environment with deterministic dynamics."""

    def __init__(self, data: pd.DataFrame | None = None, config: EnvConfig | None = None) -> None:
        self.config = config or EnvConfig()
        self.raw = data.copy() if data is not None else load_hsy_timeseries()
        self._dt_hours = self.config.timestep_minutes / 60.0
        self._cursor = 0
        self._index: pd.DatetimeIndex = self.raw.index
        self._state: SimulationState | None = None

    def reset(self, start: pd.Timestamp | None = None) -> SimulationState:
        if start is None:
            self._cursor = 0
        else:
            self._cursor = int(self._index.get_indexer_for([start])[0])
        row = self.raw.iloc[self._cursor]
        level = float(row[self.config.level_column])
        volume = self._interpolate_volume(level)
        # Price is in cents/kWh in Excel, convert to EUR/kWh
        price_cents = float(row[self.config.price_column])
        self._state = SimulationState(
            timestamp=self._index[self._cursor],
            tunnel_volume_m3=volume,
            tunnel_level_m=level,
            price_eur_per_kwh=price_cents / 100.0,  # Convert cents to EUR
            inflow_m3_per_h=float(row[self.config.inflow_column]),
            pump_flows_m3_per_h={col: float(row.get(col, 0.0)) for col in self.config.pump_flow_columns},
        )
        return self._state

    def _interpolate_volume(self, level: float) -> float:
        return tunnel_volume_from_level(level)

    def _interpolate_level(self, volume: float) -> float:
        return tunnel_level_from_volume(volume)

    def step(self, commanded_flows: Dict[str, float]) -> Tuple[SimulationState, Dict[str, float]]:
        if self._state is None:
            raise RuntimeError("Environment not reset.")
        current_row = self.raw.iloc[self._cursor]
        inflow = float(current_row[self.config.inflow_column])
        price = float(current_row[self.config.price_column]) / 100.0  # Convert cents to EUR
        safe_commands = self._sanitize_commands(commanded_flows)
        total_outflow = sum(safe_commands.values())
        next_volume = max(
            0.0,
            self._state.tunnel_volume_m3 + (inflow - total_outflow) * self._dt_hours,
        )
        next_level = self._interpolate_level(next_volume)
        energy_kwh = self._estimate_energy(current_row, safe_commands)
        self._cursor += 1
        if self._cursor >= len(self.raw):
            self._cursor = len(self.raw) - 1
        next_row = self.raw.iloc[self._cursor]
        self._state = SimulationState(
            timestamp=self._index[self._cursor],
            tunnel_volume_m3=next_volume,
            tunnel_level_m=next_level,
            price_eur_per_kwh=float(next_row[self.config.price_column]) / 100.0,  # Convert cents to EUR
            inflow_m3_per_h=float(next_row[self.config.inflow_column]),
            pump_flows_m3_per_h=safe_commands,
        )
        info = {
            "total_outflow": total_outflow,
            "inflow": inflow,
            "price": price,
            "energy_kwh": energy_kwh,
            "commands": safe_commands,
        }
        return self._state, info

    def _sanitize_commands(self, commands: Dict[str, float]) -> Dict[str, float]:
        bounded: Dict[str, float] = {}
        for col in self.config.pump_flow_columns:
            value = float(commands.get(col, 0.0))
            upper = self.config.pump_capacity_m3_per_h.get(col)
            if upper is None:
                hist = self.raw[col]
                upper = float(hist.quantile(0.99))
            bounded[col] = float(np.clip(value, 0.0, max(upper, 0.0)))
        return bounded

    def iter_history(self, columns: Iterable[str]) -> pd.DataFrame:
        return self.raw.loc[:, columns]

    def _estimate_energy(self, row: pd.Series, commands: Dict[str, float]) -> float:
        """
        Calculate energy consumption using proper pump physics.
        
        Formula from documents: E = (Q × H × ρ × g) / (η × 3600)
        Where:
        - Q = flow rate (m³/h)
        - H = pump head (m) = L2 - L1 = WWTP_level - tunnel_level
        - ρ = water density (kg/m³) = 1000
        - g = gravity (m/s²) = 9.81
        - η = pump efficiency (decimal) = 0.816 for small, 0.848 for large
        - 3600 = conversion from J/s (W) to kWh
        
        Result: kWh per timestep
        """
        energy = 0.0
        
        # Calculate pump head: H = L2 (WWTP, constant 30m) - L1 (tunnel level, varies)
        L1_tunnel_level = self._state.tunnel_level_m if self._state else 0.0
        pump_head_m = self.config.L2_WWTP_level_m - L1_tunnel_level
        
        # Ensure positive head (safety check)
        if pump_head_m <= 0:
            return 0.0
        
        for pump in self.config.pump_flow_columns:
            flow_m3_per_h = commands.get(pump, 0.0)
            
            if flow_m3_per_h <= 0:
                continue
            
            efficiency = pump_efficiency(pump, flow_m3_per_h)
            
            # Energy formula: E = (Q × H × ρ × g) / (η × 3600)
            # Q in m³/h, convert to m³/s by dividing by 3600
            flow_m3_per_s = flow_m3_per_h / 3600.0
            
            # Power in Watts: P = (Q × H × ρ × g) / η
            power_watts = (
                flow_m3_per_s 
                * pump_head_m 
                * self.config.water_density_kg_per_m3 
                * self.config.gravity_m_per_s2
            ) / efficiency
            
            # Convert to kWh: kWh = (W / 1000) × hours
            power_kw = power_watts / 1000.0
            energy_kwh_this_pump = power_kw * self._dt_hours
            
            energy += energy_kwh_this_pump
        
        return max(energy, 0.0)
