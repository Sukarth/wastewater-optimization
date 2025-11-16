"""
Quick Demo: Intelligent Wastewater Pumping Optimization
========================================================

Runs a 24-hour simulation comparing multi-agent AI system vs. baseline reactive control.

This demonstrates:
- Cost savings through intelligent scheduling
- Safety-compliant operation
- Strategic use of low electricity price periods

Usage:
    python demo.py

Output:
    - Console: Performance comparison metrics
    - Files: results/improved_multi_agent.csv and results/improved_baseline.csv

For interactive visualization, run: streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from src.agents.coordinator import CoordinatorConfig, MultiAgentCoordinator

# Initialize coordinator with default configuration
coordinator = MultiAgentCoordinator(CoordinatorConfig())

print("=" * 70)
print("  INTELLIGENT WASTEWATER PUMPING OPTIMIZATION - DEMO")
print("  Junction 2025 | HSY x Valmet Challenge")
print("=" * 70)
print("\nRunning 24-hour simulation (Nov 15, 2024)...")
print("  - Multi-Agent AI: Forecaster + Planner + Safety")
print("  - Baseline: Reactive threshold-based control")
print("  - Timestep: 15 minutes (96 steps)")
print()

# Run simulations (96 steps = 24 hours at 15-min intervals)
multi_agent = coordinator.run_multi_agent(steps=96, start=pd.Timestamp("2024-11-15 00:00"))
baseline = coordinator.run_baseline(steps=96, start=pd.Timestamp("2024-11-15 00:00"))

# Calculate metrics
ma_cost = (multi_agent['energy_kwh'] * multi_agent['price_eur_kwh']).sum()
ma_energy = multi_agent['energy_kwh'].sum()
ma_avg_level = multi_agent['level_m'].mean()

bl_cost = (baseline['energy_kwh'] * baseline['price_eur_kwh']).sum()
bl_energy = baseline['energy_kwh'].sum()
bl_avg_level = baseline['level_m'].mean()

savings_pct = ((bl_cost - ma_cost) / bl_cost) * 100
energy_pct = ((bl_energy - ma_energy) / bl_energy) * 100

# Display results
print("=" * 70)
print("  RESULTS")
print("=" * 70)
print(f"\n{'Strategy':<15} {'Cost (EUR)':<12} {'Energy (kWh)':<15} {'Avg Level (m)':<15}")
print("-" * 70)
print(f"{'Multi-Agent':<15} {ma_cost:<12.2f} {ma_energy:<15.1f} {ma_avg_level:<15.2f}")
print(f"{'Baseline':<15} {bl_cost:<12.2f} {bl_energy:<15.1f} {bl_avg_level:<15.2f}")
print("-" * 70)
print(f"{'Savings':<15} {bl_cost - ma_cost:<12.2f} {bl_energy - ma_energy:<15.1f} {ma_avg_level - bl_avg_level:<15.2f}")
print()

# Interpret results
print("=" * 70)
print("  ANALYSIS")
print("=" * 70)
print(f"\nCost Savings:   {savings_pct:+.1f}% ({bl_cost - ma_cost:+.2f} EUR/day)")
print(f"Energy Change:  {energy_pct:+.1f}% ({bl_energy - ma_energy:+.1f} kWh/day)")
print(f"Level Change:   {(ma_avg_level - bl_avg_level) / bl_avg_level * 100:+.1f}% ({ma_avg_level - bl_avg_level:+.3f} m)")

if ma_avg_level > bl_avg_level:
    print(f"\n[GOOD] Multi-agent maintains HIGHER tunnel level ({ma_avg_level:.2f}m vs {bl_avg_level:.2f}m)")
    print("       Lower pump head = better efficiency & equipment longevity")
else:
    print(f"\n[WARNING] Multi-agent maintains LOWER tunnel level ({ma_avg_level:.2f}m vs {bl_avg_level:.2f}m)")
    print("          Higher pump head = worse efficiency")

print("\nKey Insight:")
if savings_pct > 0:
    print(f"  The multi-agent system saves {savings_pct:.1f}% in costs by intelligently")
    print("  scheduling pumping during low electricity price periods.")
    if energy_pct < 0:
        print(f"  Energy consumption increased {abs(energy_pct):.1f}%, but total COST is lower")
        print("  because pumping happens when electricity is cheapest (price arbitrage).")
else:
    print("  Results are close. Savings vary with electricity price volatility.")

# Save detailed results
print("\n" + "=" * 70)
print("  OUTPUT FILES")
print("=" * 70)
multi_agent.to_csv("results/improved_multi_agent.csv", index=False)
baseline.to_csv("results/improved_baseline.csv", index=False)
print("\n[SUCCESS] Detailed results saved:")
print("  - results/improved_multi_agent.csv")
print("  - results/improved_baseline.csv")

print("\n" + "=" * 70)
print("  NEXT STEPS")
print("=" * 70)
print("\nFor interactive visualization, run:")
print("  streamlit run dashboard/app.py")
print("\nFor full documentation, see:")
print("  README.md")
print("\n" + "=" * 70)

