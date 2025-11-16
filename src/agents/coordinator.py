"""Coordinator for multi-agent control loop."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
import numpy as np

from src.data.loader import derive_pump_bounds, load_hsy_timeseries
from src.simulation.baseline import ThresholdPolicyConfig, threshold_controller
from src.simulation.environment import DigitalTwinEnv, SimulationState
from src.agents.forecast import ForecastAgent, ForecastConfig
from src.agents.planner import PlannerAgent, PlannerConfig
from src.agents.safety import SafetyAgent, SafetyConfig


@dataclass
class CoordinatorConfig:
    horizon_steps: int = 24
    baseline_high_level: float = 6.5
    baseline_low_level: float = 2.0
    pump_nominal_flow: float = 350.0
    multi_safety_config: SafetyConfig | None = None
    baseline_safety_config: SafetyConfig | None = None


class MultiAgentCoordinator:
    def __init__(self, config: CoordinatorConfig | None = None, history: pd.DataFrame | None = None) -> None:
        self.config = config or CoordinatorConfig()
        self.history = history.copy() if history is not None else load_hsy_timeseries()
        base_env = DigitalTwinEnv(self.history)
        self.env_config = base_env.config
        forecast_cfg = ForecastConfig(horizon_steps=self.config.horizon_steps)
        self.forecaster = ForecastAgent(self.history, forecast_cfg)
        pump_bounds = {
            col: (
                derive_pump_bounds(self.history, col).min_flow_m3_per_h,
                derive_pump_bounds(self.history, col).max_flow_m3_per_h,
            )
            for col in self.env_config.pump_flow_columns
        }
        planner_cfg = PlannerConfig(horizon_steps=self.config.horizon_steps)
        self.planner = PlannerAgent(self.history, self.env_config, pump_bounds, planner_cfg)
        multi_cfg = self.config.multi_safety_config or SafetyConfig(
            min_level_m=0.5,  # Updated to 0.5m per HSY (safe level, 0.0m is dry-run preventer)
            daily_flush_level_m=0.5,  # Flush to safe level during DRY weather
            post_flush_hold_level_m=2.5,
            post_flush_hold_steps=12,
            min_total_flow_m3_per_h=0.0,
            min_flow_level_buffer_m=0.0,
        )
        baseline_cfg = self.config.baseline_safety_config or SafetyConfig()
        self.multi_safety_config = multi_cfg
        self.baseline_safety_config = baseline_cfg
        self.safety = SafetyAgent(self.env_config, self.multi_safety_config)
        self.event_log: List[Dict[str, object]] = []

    def _make_env(self) -> DigitalTwinEnv:
        return DigitalTwinEnv(self.history, self.env_config)

    def run_multi_agent(self, steps: int, start: pd.Timestamp | None = None) -> pd.DataFrame:
        env = self._make_env()
        state = env.reset(start)
        self.safety = SafetyAgent(self.env_config, self.multi_safety_config)
        records: List[Dict[str, float]] = []
        self.event_log = []
        for _ in range(steps):
            forecasts = self.forecaster.predict(state.timestamp)
            self._log(
                "ForecastAgent",
                state.timestamp,
                f"Projected inflow avg {np.mean(forecasts['inflow']):.1f} m³/h, price avg {np.mean(forecasts['price']):.2f} €/kWh",
            )
            plan = self.planner.plan(state, forecasts)
            planned_outflow = sum(plan.values())
            self._log(
                "PlannerAgent",
                state.timestamp,
                f"Optimized outflow {planned_outflow:.1f} m³/h with horizon {self.planner.config.horizon_steps}",
            )
            safe_plan = self.safety.enforce(state, plan)
            if safe_plan != plan:
                self._log("SafetyAgent", state.timestamp, "Adjusted commands to respect safety margins")
            next_state, info = env.step(safe_plan)
            self.safety.post_step(next_state, info["commands"])
            records.append(
                {
                    "timestamp": state.timestamp,
                    "level_m": state.tunnel_level_m,
                    "volume_m3": state.tunnel_volume_m3,
                    "price_eur_kwh": state.price_eur_per_kwh,
                    "inflow_m3_h": state.inflow_m3_per_h,
                    "outflow_m3_h": info["total_outflow"],
                    "energy_kwh": info["energy_kwh"],
                    "strategy": "multi_agent",
                }
            )
            for pump, value in info["commands"].items():
                records[-1][f"{pump}_flow"] = value
            state = next_state
        return pd.DataFrame(records).set_index("timestamp")

    def run_baseline(self, steps: int, start: pd.Timestamp | None = None) -> pd.DataFrame:
        env = self._make_env()
        state = env.reset(start)
        safety = SafetyAgent(self.env_config, self.baseline_safety_config)
        cfg = ThresholdPolicyConfig(
            level_high_m=self.config.baseline_high_level,
            level_low_m=self.config.baseline_low_level,
            level_optimal_m=3.5,  # Target optimal level for energy efficiency
            pump_on_flow_m3_per_h=self.config.pump_nominal_flow,
        )
        records: List[Dict[str, float]] = []
        for _ in range(steps):
            commands = threshold_controller(state, env, cfg)
            safe_commands = safety.enforce(state, commands)
            next_state, info = env.step(safe_commands)
            safety.post_step(next_state, info["commands"])
            records.append(
                {
                    "timestamp": state.timestamp,
                    "level_m": state.tunnel_level_m,
                    "volume_m3": state.tunnel_volume_m3,
                    "price_eur_kwh": state.price_eur_per_kwh,
                    "inflow_m3_h": state.inflow_m3_per_h,
                    "outflow_m3_h": info["total_outflow"],
                    "energy_kwh": info["energy_kwh"],
                    "strategy": "baseline",
                }
            )
            for pump, value in info["commands"].items():
                records[-1][f"{pump}_flow"] = value
            state = next_state
        return pd.DataFrame(records).set_index("timestamp")

    def _log(self, agent: str, timestamp: pd.Timestamp, message: str) -> None:
        self.event_log.append({"timestamp": timestamp, "agent": agent, "message": message})

    def get_event_log(self) -> pd.DataFrame:
        if not self.event_log:
            return pd.DataFrame(columns=["timestamp", "agent", "message"])
        df = pd.DataFrame(self.event_log)
        return df.sort_values("timestamp").reset_index(drop=True)
