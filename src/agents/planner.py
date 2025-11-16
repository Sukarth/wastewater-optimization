"""Optimization-based planner agent using linear programming."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd
import pulp

from src.simulation.environment import EnvConfig, SimulationState
from src.utils.pumps import nominal_flow_m3_per_h, pump_efficiency
from src.utils.volume import tunnel_volume_from_level


@dataclass
class PlannerConfig:
    horizon_steps: int = 8
    volume_safety_margin: float = 50.0  # m³
    ramp_limit_m3_per_h: float = 150.0
    level_penalty_weight: float = 180.0  # Penalty for deviating from optimal level
    target_level_m: float = 3.8  # Target level to minimize pump head
    operational_min_level_m: float = 1.2  # Soft lower bound - keep tunnel reasonably full
    operational_level_penalty_weight: float = 800.0  # Strong penalty against draining too low
    min_pump_runtime_steps: int = 8  # Minimum 2 hours = 8 timesteps of 15min
    flow_smoothness_weight: float = 10.0  # Penalty for large flow changes
    constant_flow_penalty_weight: float = 25.0
    flow_change_penalty_weight: float = 40.0
    pump_usage_balance_weight: float = 5.0
    min_total_flow_m3_per_h: float = 1400.0
    max_total_flow_m3_per_h: float = 16000.0  # Max F2 = 16000 m³/h = 5 big pumps (per challenge update)
    volume_penalty_weight: float = 60.0  # Moderate penalty against volume deficits
    volume_excess_weight: float = 8.0
    final_volume_slack_m3: float = 2000.0


class PlannerAgent:
    def __init__(
        self,
        history: pd.DataFrame,
        env_config: EnvConfig,
        pump_bounds: Dict[str, tuple[float, float]],
        config: PlannerConfig | None = None,
    ) -> None:
        self.history = history
        self.env_config = env_config
        self.pump_bounds = pump_bounds
        self.config = config or PlannerConfig()
        self._dt_hours = env_config.timestep_minutes / 60.0
        
        # Use real pump efficiencies from Grundfos curves (NOT the "efficiency" column in data)
        self._pump_nominal_flow = {
            pump: nominal_flow_m3_per_h(pump)
            for pump in env_config.pump_flow_columns
        }
        self._pump_nominal_efficiency = {
            pump: pump_efficiency(pump, self._pump_nominal_flow.get(pump, 1.0))
            for pump in env_config.pump_flow_columns
        }

    def _volume_from_level(self, level: float) -> float:
        return tunnel_volume_from_level(level)

    def plan(self, state: SimulationState, forecasts: Dict[str, np.ndarray]) -> Dict[str, float]:
        inflow = forecasts["inflow"]
        price = forecasts["price"]
        horizon = min(len(inflow), self.config.horizon_steps)
        pumps = list(self.env_config.pump_flow_columns)
        problem = pulp.LpProblem("PumpScheduling", pulp.LpMinimize)
        
        # Decision variables: pump flows and binary activation at each timestep
        flow_vars: Dict[tuple[str, int], pulp.LpVariable] = {}
        on_vars: Dict[tuple[str, int], pulp.LpVariable] = {}
        for t in range(horizon):
            for pump in pumps:
                lb, ub = self.pump_bounds.get(pump, (0.0, 500.0))
                flow_vars[(pump, t)] = pulp.LpVariable(f"f_{pump}_{t}", lowBound=max(lb, 0.0), upBound=max(ub, 0.0))
                on_vars[(pump, t)] = pulp.LpVariable(f"on_{pump}_{t}", lowBound=0, upBound=1, cat="Binary")
                min_full = self.env_config.pump_min_full_speed_m3_per_h.get(pump, 0.0)
                capacity = self.env_config.pump_capacity_m3_per_h.get(pump, max(ub, 0.0))
                if min_full > 0:
                    problem += flow_vars[(pump, t)] >= min_full * on_vars[(pump, t)], f"min_full_{pump}_{t}"
                problem += flow_vars[(pump, t)] <= capacity * on_vars[(pump, t)], f"capacity_{pump}_{t}"

        # Initial conditions
        initial_volume = state.tunnel_volume_m3
        initial_level = state.tunnel_level_m
        
        min_volume = self._volume_from_level(self.env_config.min_tunnel_level_m) + self.config.volume_safety_margin
        max_volume = self._volume_from_level(self.env_config.max_tunnel_level_m) - self.config.volume_safety_margin
        if max_volume <= min_volume:
            max_volume = min_volume + 500.0
        
        op_lower = min_volume + 10.0
        op_upper = max_volume - 200.0
        if op_upper <= op_lower:
            op_upper = op_lower + 10.0
        operational_min_volume = np.clip(
            self._volume_from_level(self.config.operational_min_level_m),
            op_lower,
            op_upper,
        )
        target_lower = operational_min_volume + 100.0
        target_upper = max_volume - 100.0
        if target_upper <= target_lower:
            target_upper = target_lower + 10.0
        target_volume = np.clip(
            self._volume_from_level(self.config.target_level_m),
            target_lower,
            target_upper,
        )
        
        # Objective: minimize total cost with penalty for low volumes
        objective_terms: List[pulp.LpAffineExpression] = []
        
        # Physical constants
        rho_g = self.env_config.water_density_kg_per_m3 * self.env_config.gravity_m_per_s2
        current_head = self.env_config.L2_WWTP_level_m - initial_level
        
        # Track cumulative volume for constraints
        cumulative_volume = initial_volume
        
        enforce_constancy = self.config.constant_flow_penalty_weight > 0.0
        target_flow = 0.0
        if enforce_constancy:
            target_flow = float(np.clip(
                np.mean(inflow[:horizon]) if horizon else 0.0,
                self.config.min_total_flow_m3_per_h,
                self.config.max_total_flow_m3_per_h,
            ))
        flow_dev_pos: Dict[int, pulp.LpVariable] = {}
        flow_dev_neg: Dict[int, pulp.LpVariable] = {}
        flow_change_pos: Dict[int, pulp.LpVariable] = {}
        flow_change_neg: Dict[int, pulp.LpVariable] = {}
        volume_deficit_vars: Dict[int, pulp.LpVariable] = {}
        volume_excess_vars: Dict[int, pulp.LpVariable] = {}
        operational_deficit_vars: Dict[int, pulp.LpVariable] = {}

        for t in range(horizon):
            # Calculate total outflow at this timestep
            total_outflow_t = pulp.lpSum(flow_vars[(pump, t)] for pump in pumps)
            if enforce_constancy:
                flow_dev_pos[t] = pulp.LpVariable(f"flow_dev_pos_{t}", lowBound=0)
                flow_dev_neg[t] = pulp.LpVariable(f"flow_dev_neg_{t}", lowBound=0)
                problem += (
                    total_outflow_t - target_flow == flow_dev_pos[t] - flow_dev_neg[t]
                ), f"flow_constancy_{t}"
                objective_terms.append(
                    self.config.constant_flow_penalty_weight * (flow_dev_pos[t] + flow_dev_neg[t])
                )
            problem += total_outflow_t >= self.config.min_total_flow_m3_per_h, f"min_total_flow_{t}"
            problem += total_outflow_t <= self.config.max_total_flow_m3_per_h, f"max_total_flow_{t}"
            
            # Update cumulative volume
            cumulative_volume = cumulative_volume + (inflow[t] - total_outflow_t) * self._dt_hours
            
            # Volume constraints
            problem += cumulative_volume >= min_volume, f"min_vol_{t}"
            problem += cumulative_volume <= max_volume, f"max_vol_{t}"
            
            # Cost for each pump
            for pump in pumps:
                efficiency = self._pump_nominal_efficiency.get(pump, 0.80)
                flow = flow_vars[(pump, t)]
                
                # Base energy cost at current head
                base_cost_per_m3h = (current_head * rho_g * price[t] * self._dt_hours) / (efficiency * 3.6e6)
                objective_terms.append(base_cost_per_m3h * flow)
            
            volume_deficit_vars[t] = pulp.LpVariable(f"volume_deficit_{t}", lowBound=0)
            problem += (
                volume_deficit_vars[t] >= target_volume - cumulative_volume
            ), f"volume_deficit_constraint_{t}"
            objective_terms.append(self.config.volume_penalty_weight * volume_deficit_vars[t])
            volume_excess_vars[t] = pulp.LpVariable(f"volume_excess_{t}", lowBound=0)
            problem += (
                volume_excess_vars[t] >= cumulative_volume - target_volume
            ), f"volume_excess_constraint_{t}"
            objective_terms.append(self.config.volume_excess_weight * volume_excess_vars[t])
            operational_deficit_vars[t] = pulp.LpVariable(f"operational_deficit_{t}", lowBound=0)
            problem += (
                operational_deficit_vars[t] >= operational_min_volume - cumulative_volume
            ), f"operational_min_volume_constraint_{t}"
            objective_terms.append(self.config.operational_level_penalty_weight * operational_deficit_vars[t])
        
        problem += pulp.lpSum(objective_terms)

        # Final volume should be close to initial (avoid runaway drift)
        slack = max(0.0, self.config.final_volume_slack_m3)
        problem += cumulative_volume >= initial_volume - slack, "final_vol_min"
        problem += cumulative_volume <= initial_volume + slack, "final_vol_max"

        # Ramp constraints (smooth flow changes)
        for t in range(1, horizon):
            for pump in pumps:
                problem += (
                    flow_vars[(pump, t)] - flow_vars[(pump, t - 1)]
                    <= self.config.ramp_limit_m3_per_h
                ), f"ramp_up_{pump}_{t}"
                problem += (
                    flow_vars[(pump, t - 1)] - flow_vars[(pump, t)]
                    <= self.config.ramp_limit_m3_per_h
                ), f"ramp_down_{pump}_{t}"
        
        # Flow smoothness: penalize changes in total outflow
        for t in range(1, horizon):
            total_flow_t = pulp.lpSum(flow_vars[(pump, t)] for pump in pumps)
            total_flow_prev = pulp.lpSum(flow_vars[(pump, t-1)] for pump in pumps)
            flow_change = total_flow_t - total_flow_prev
            problem += flow_change <= self.config.ramp_limit_m3_per_h, f"smooth_up_{t}"
            problem += -flow_change <= self.config.ramp_limit_m3_per_h, f"smooth_down_{t}"
            if self.config.flow_change_penalty_weight > 0:
                flow_change_pos[t] = pulp.LpVariable(f"flow_change_pos_{t}", lowBound=0)
                flow_change_neg[t] = pulp.LpVariable(f"flow_change_neg_{t}", lowBound=0)
                problem += flow_change == flow_change_pos[t] - flow_change_neg[t], f"flow_change_balance_{t}"
                objective_terms.append(
                    self.config.flow_change_penalty_weight * (flow_change_pos[t] + flow_change_neg[t])
                )

        # Balance pump usage so daily runtime stays even
        if self.config.pump_usage_balance_weight > 0 and pumps:
            total_on_time = pulp.lpSum(on_vars[(pump, t)] for pump in pumps for t in range(horizon))
            avg_on_time = total_on_time / float(len(pumps))
            for pump in pumps:
                usage = pulp.lpSum(on_vars[(pump, t)] for t in range(horizon))
                usage_dev_pos = pulp.LpVariable(f"usage_dev_pos_{pump}", lowBound=0)
                usage_dev_neg = pulp.LpVariable(f"usage_dev_neg_{pump}", lowBound=0)
                problem += usage - avg_on_time == usage_dev_pos - usage_dev_neg, f"usage_balance_{pump}"
                objective_terms.append(
                    self.config.pump_usage_balance_weight * (usage_dev_pos + usage_dev_neg)
                )

        # Solve
        solver = pulp.PULP_CBC_CMD(msg=False)
        problem.solve(solver)

        first_step = {pump: flow_vars[(pump, 0)].value() or 0.0 for pump in pumps}
        return first_step
