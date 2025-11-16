"""Simple rule-based baseline controllers for comparison."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from src.simulation.environment import DigitalTwinEnv, SimulationState


@dataclass
class ThresholdPolicyConfig:
    level_high_m: float = 6.5  # Pump aggressively above this
    level_low_m: float = 2.0   # Stop pumping below this
    level_optimal_m: float = 3.5  # Target level for efficiency
    pump_on_flow_m3_per_h: float = 350.0  # Per-pump flow when high


def threshold_controller(state: SimulationState, env: DigitalTwinEnv, cfg: ThresholdPolicyConfig) -> Dict[str, float]:
    """
    Improved baseline controller that maintains optimal level for energy efficiency.
    
    Strategy:
    - Keep tunnel level near 3.5m (balances safety and energy efficiency)
    - Higher level = lower pump head = less energy per m³
    - Responds to inflow but maintains target level
    """
    commands: Dict[str, float] = {pump: 0.0 for pump in env.config.pump_flow_columns}
    
    level = state.tunnel_level_m
    inflow = state.inflow_m3_per_h
    
    # Emergency high level: pump aggressively
    if level >= cfg.level_high_m:
        for pump in commands:
            commands[pump] = cfg.pump_on_flow_m3_per_h
    
    # Emergency low level: stop pumping (let it fill)
    elif level <= cfg.level_low_m:
        for pump in commands:
            commands[pump] = 0.0
    
    # Normal operation: maintain optimal level around 3.5m
    else:
        # Target: keep level stable near optimal
        level_error = level - cfg.level_optimal_m
        
        # Proportional control: adjust pumping based on level deviation
        # If level > optimal: pump more
        # If level < optimal: pump less
        base_flow = inflow  # Match inflow as baseline
        
        # Adjustment: pump extra when above target, less when below
        adjustment = level_error * 200.0  # m³/h per meter of deviation
        total_flow = max(base_flow + adjustment, 0.0)
        
        # Distribute across pumps
        per_pump = total_flow / len(commands)
        for pump in commands:
            commands[pump] = per_pump
    
    return commands
