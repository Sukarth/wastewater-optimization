"""Safety-focused post-processor for planner commands."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

import pandas as pd

from src.simulation.environment import EnvConfig, SimulationState
from src.utils.volume import tunnel_volume_from_level


@dataclass
class SafetyConfig:
    min_reserve_ratio: float = 0.1
    max_level_m: float = 7.5
    min_level_m: float = 0.5  # Safe level per Mika 11/15: "Safe level is 0.5m" (0.0m is dry-run preventer)
    daily_flush_level_m: float = 0.5
    flush_enforcement_hour: int = 10  # hour of day when flush enforcement begins
    flush_deadline_buffer_steps: int = 4  # force flush if this many steps remain
    flush_inflow_threshold_m3_per_h: float = 2200.0
    max_flush_flow_m3_per_h: float = 12000.0
    flush_volume_step_m3: float = 2000.0
    flush_completion_tolerance_m3: float = 150.0
    post_flush_hold_level_m: float = 1.8
    post_flush_hold_steps: int = 12  # number of timesteps to guard refilling
    storm_inflow_threshold_m3_per_h: float = 2600.0
    storm_relief_steps: int = 12  # duration to defer flush once high inflow detected
    min_total_flow_m3_per_h: float = 1400.0
    min_flow_level_buffer_m: float = 0.2
    min_runtime_steps: int = 8
    min_rest_steps: int = 8
    activation_threshold_m3_per_h: float = 50.0


class SafetyAgent:
    def __init__(self, env_config: EnvConfig, config: SafetyConfig | None = None) -> None:
        self.env_config = env_config
        self.config = config or SafetyConfig()
        pumps = list(env_config.pump_flow_columns)
        self._pump_runtime_steps: Dict[str, int] = {pump: 0 for pump in pumps}
        self._pump_daily_runtime_steps: Dict[str, int] = {pump: 0 for pump in pumps}
        self._pump_last_state: Dict[str, bool] = {pump: False for pump in pumps}
        self._pump_rest_steps: Dict[str, int] = {pump: self.config.min_rest_steps for pump in pumps}
        self._current_day: date | None = None
        self.timesteps_since_flush: int = 0
        self.last_flush_time: pd.Timestamp | None = None
        self._flushed_today: bool = False
        self._pending_flush: bool = False
        self._dt_hours = self.env_config.timestep_minutes / 60.0
        self._flush_active: bool = False
        self._flush_target_volume: float = self._volume_from_level(self.config.daily_flush_level_m)
        self._post_flush_hold_steps: int = 0
        self._post_flush_hold_new: bool = False
        self._storm_steps_remaining: int = 0

    def enforce(self, state: SimulationState, commands: Dict[str, float]) -> Dict[str, float]:
        self._maybe_reset_daily(state.timestamp.date())
        base = {
            pump: max(0.0, float(commands.get(pump, 0.0)))
            for pump in self.env_config.pump_flow_columns
        }
        base = self._clip_to_capacities(base)
        hold_active = (
            self._post_flush_hold_steps > 0
            and state.tunnel_level_m < self.config.post_flush_hold_level_m
        )
        level_critical = state.tunnel_level_m <= self.config.min_level_m or hold_active
        desired_total = 0.0 if level_critical else sum(base.values())

        if self._should_force_flush(state):
            safe = self._command_full_flush(state)
        elif level_critical:
            safe = {pump: 0.0 for pump in base}
        else:
            safe = self._allocate_balanced_flows(desired_total)
            safe = self._apply_runtime_frequency_and_capacity(safe)

        safe = self._protect_levels(state, safe)
        safe = self._limit_total_capacity(safe)
        safe = self._ensure_minimum_operational_flow(state, safe)
        return safe

    def post_step(self, next_state: SimulationState, executed_commands: Dict[str, float]) -> None:
        self._maybe_reset_daily(next_state.timestamp.date())
        self.timesteps_since_flush += 1
        if next_state.inflow_m3_per_h >= self.config.storm_inflow_threshold_m3_per_h:
            self._storm_steps_remaining = max(self._storm_steps_remaining, self.config.storm_relief_steps)
        elif self._storm_steps_remaining > 0:
            self._storm_steps_remaining = max(0, self._storm_steps_remaining - 1)
        tolerance = self.config.flush_completion_tolerance_m3
        if next_state.tunnel_volume_m3 <= self._flush_target_volume + tolerance:
            self._complete_flush(next_state.timestamp)
        elif self._post_flush_hold_steps > 0:
            hold_level = self.config.post_flush_hold_level_m
            if next_state.tunnel_level_m >= hold_level:
                self._post_flush_hold_steps = 0
                self._post_flush_hold_new = False
            elif not self._post_flush_hold_new:
                self._post_flush_hold_steps = max(0, self._post_flush_hold_steps - 1)
            else:
                self._post_flush_hold_new = False

        for pump, flow in executed_commands.items():
            is_on = flow >= self.config.activation_threshold_m3_per_h
            if is_on:
                self._pump_runtime_steps[pump] += 1
                self._pump_daily_runtime_steps[pump] += 1
                self._pump_rest_steps[pump] = 0
            else:
                self._pump_runtime_steps[pump] = 0
                self._pump_rest_steps[pump] += 1
            self._pump_last_state[pump] = is_on

    # --- helpers -----------------------------------------------------------------

    def _maybe_reset_daily(self, current_day: date) -> None:
        if self._current_day == current_day:
            return
        if self._current_day is not None and not self._flushed_today:
            self._pending_flush = True
        self._current_day = current_day
        self._flushed_today = False
        self._flush_active = False
        self._post_flush_hold_steps = 0
        self._post_flush_hold_new = False
        for pump in self._pump_daily_runtime_steps:
            self._pump_daily_runtime_steps[pump] = 0

    def _clip_to_capacities(self, flows: Dict[str, float]) -> Dict[str, float]:
        for pump in flows:
            capacity = self.env_config.pump_capacity_m3_per_h.get(pump)
            if capacity is not None:
                flows[pump] = min(flows[pump], capacity)
            flows[pump] = max(0.0, flows[pump])
        return flows

    def _should_force_flush(self, state: SimulationState) -> bool:
        if self._storm_steps_remaining > 0:
            return False
        if self._flush_active:
            return True
        if state.tunnel_level_m <= self.config.daily_flush_level_m:
            return False
        if self._flushed_today:
            return False
        if self._pending_flush:
            return True
        hour = state.timestamp.hour
        if hour >= self.config.flush_enforcement_hour:
            return True
        if (
            state.inflow_m3_per_h <= self.config.flush_inflow_threshold_m3_per_h
            and hour >= max(0, self.config.flush_enforcement_hour - 2)
        ):
            return True
        steps_left = self._steps_remaining_in_day(state.timestamp)
        if steps_left <= self.config.flush_deadline_buffer_steps:
            return True
        return False

    def _command_full_flush(self, state: SimulationState) -> Dict[str, float]:
        if not self._flush_active:
            self._start_flush(state)
        target_volume = self._flush_target_volume
        current_volume = state.tunnel_volume_m3
        volume_to_remove = max(0.0, current_volume - target_volume)
        tolerance = self.config.flush_completion_tolerance_m3
        if volume_to_remove <= tolerance:
            self._complete_flush(state.timestamp)
            return {pump: 0.0 for pump in self.env_config.pump_flow_columns}
        step_volume = min(volume_to_remove, self.config.flush_volume_step_m3)
        required_total_outflow = (step_volume / max(self._dt_hours, 1e-6)) + state.inflow_m3_per_h
        max_capacity = sum(
            self.env_config.pump_capacity_m3_per_h.get(pump, 0.0)
            for pump in self.env_config.pump_flow_columns
        )
        flush_cap = min(max_capacity, self.config.max_flush_flow_m3_per_h)
        required_total_outflow = min(required_total_outflow, flush_cap)
        # Ensure at least one pump runs at minimum full-speed to start the flush
        min_full_values = [
            self.env_config.pump_min_full_speed_m3_per_h.get(pump, 0.0)
            for pump in self.env_config.pump_flow_columns
            if self.env_config.pump_min_full_speed_m3_per_h.get(pump, 0.0) > 0
        ]
        min_operational = min(min_full_values) if min_full_values else self.config.activation_threshold_m3_per_h
        required_total_outflow = max(required_total_outflow, min_operational)
        return self._allocate_balanced_flows(required_total_outflow)

    def _allocate_balanced_flows(self, total_flow: float) -> Dict[str, float]:
        flows = {pump: 0.0 for pump in self.env_config.pump_flow_columns}
        if total_flow <= 0:
            return flows
        max_total = sum(
            self.env_config.pump_capacity_m3_per_h.get(pump, 0.0)
            for pump in self.env_config.pump_flow_columns
        )
        remaining = min(total_flow, max_total)
        pumps_sorted = sorted(
            flows.keys(),
            key=lambda p: (
                self._pump_daily_runtime_steps.get(p, 0),
                self._pump_runtime_steps.get(p, 0),
            ),
        )
        for pump in pumps_sorted:
            if remaining <= 0:
                break
            capacity = self.env_config.pump_capacity_m3_per_h.get(pump, 0.0)
            min_full = self.env_config.pump_min_full_speed_m3_per_h.get(pump, 0.0)
            if capacity <= 0:
                continue
            base_flow = min(capacity, max(min_full, remaining))
            flows[pump] = base_flow
            remaining -= base_flow
        if remaining > 0:
            for pump in pumps_sorted:
                if remaining <= 0:
                    break
                capacity = self.env_config.pump_capacity_m3_per_h.get(pump, 0.0)
                extra_cap = max(0.0, capacity - flows[pump])
                if extra_cap <= 0:
                    continue
                extra = min(extra_cap, remaining)
                flows[pump] += extra
                remaining -= extra
        return flows

    def _apply_runtime_frequency_and_capacity(self, flows: Dict[str, float]) -> Dict[str, float]:
        for pump in flows:
            capacity = self.env_config.pump_capacity_m3_per_h.get(pump, 0.0)
            min_full = self.env_config.pump_min_full_speed_m3_per_h.get(pump, 0.0)
            command = flows[pump]
            currently_on = self._pump_last_state.get(pump, False)
            runtime = self._pump_runtime_steps.get(pump, 0)
            rest = self._pump_rest_steps.get(pump, self.config.min_rest_steps)
            wants_on = command >= self.config.activation_threshold_m3_per_h
            if wants_on and not currently_on and rest < self.config.min_rest_steps:
                wants_on = False
                command = 0.0
            if currently_on and runtime < self.config.min_runtime_steps and not wants_on:
                wants_on = True
                command = max(command, min_full)
            if wants_on and command < min_full:
                if currently_on:
                    command = min_full
                else:
                    wants_on = False
                    command = 0.0
            if capacity > 0:
                command = min(command, capacity)
            flows[pump] = command if wants_on else 0.0
        return flows

    def _protect_levels(self, state: SimulationState, flows: Dict[str, float]) -> Dict[str, float]:
        total = sum(flows.values())
        if state.tunnel_level_m >= self.config.max_level_m:
            scale = 1.0 + self.config.min_reserve_ratio
            for pump in flows:
                capacity = self.env_config.pump_capacity_m3_per_h.get(pump, flows[pump])
                flows[pump] = min(capacity, flows[pump] * scale)
        elif state.tunnel_level_m <= self.config.min_level_m:
            for pump in flows:
                flows[pump] = 0.0
        return flows

    def _limit_total_capacity(self, flows: Dict[str, float]) -> Dict[str, float]:
        total_safe = sum(flows.values())
        max_total_flow = sum(self.env_config.pump_capacity_m3_per_h.get(p, 0.0) for p in flows)
        if max_total_flow <= 0 or total_safe <= max_total_flow:
            return flows
        scale = max_total_flow / total_safe
        for pump in flows:
            flows[pump] *= scale
        return flows

    def _ensure_minimum_operational_flow(self, state: SimulationState, flows: Dict[str, float]) -> Dict[str, float]:
        if self._flush_active or self._post_flush_hold_steps > 0:
            return flows
        if state.tunnel_level_m <= self.config.min_level_m + self.config.min_flow_level_buffer_m:
            return flows
        total = sum(flows.values())
        if total >= self.config.min_total_flow_m3_per_h:
            return flows
        lead = self._select_lead_pump()
        if lead is None:
            return flows
        min_full = self.env_config.pump_min_full_speed_m3_per_h.get(lead, 0.0)
        if min_full <= 0:
            return flows
        flows[lead] = max(flows.get(lead, 0.0), min_full)
        return flows

    def _select_lead_pump(self) -> Optional[str]:
        pumps = list(self.env_config.pump_flow_columns)
        if not pumps:
            return None
        pumps.sort(
            key=lambda p: (
                self.env_config.pump_capacity_m3_per_h.get(p, 0.0),
                self._pump_daily_runtime_steps.get(p, 0),
                self._pump_runtime_steps.get(p, 0),
            )
        )
        return pumps[0]

    def _start_flush(self, state: SimulationState) -> None:
        self._flush_active = True
        self._pending_flush = False
        self._flush_target_volume = self._volume_from_level(self.config.daily_flush_level_m)

    def _complete_flush(self, timestamp: pd.Timestamp) -> None:
        self._flush_active = False
        self._pending_flush = False
        self._flushed_today = True
        self.timesteps_since_flush = 0
        self.last_flush_time = timestamp
        if self.config.post_flush_hold_steps > 0:
            self._post_flush_hold_steps = self.config.post_flush_hold_steps
            self._post_flush_hold_new = True
        else:
            self._post_flush_hold_steps = 0
            self._post_flush_hold_new = False

    def _steps_remaining_in_day(self, timestamp: pd.Timestamp) -> int:
        next_midnight = (timestamp + pd.Timedelta(days=1)).normalize()
        delta = next_midnight - timestamp
        step_seconds = self.env_config.timestep_minutes * 60
        return max(0, int(delta.total_seconds() // step_seconds))

    def _volume_from_level(self, level: float) -> float:
        return tunnel_volume_from_level(level)
