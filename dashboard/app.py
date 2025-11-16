"""Streamlit dashboard for Intelligent Flow Optimization demo."""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import altair as alt
import pandas as pd
import streamlit as st

from src.agents.coordinator import CoordinatorConfig, MultiAgentCoordinator
from src.data.loader import load_hsy_timeseries
from src.utils.metrics import compare_strategies

st.set_page_config(page_title="Intelligent Flow Optimization", layout="wide")


@st.cache_resource
def get_history() -> pd.DataFrame:
    return load_hsy_timeseries()


@st.cache_data(show_spinner=False)
def run_simulation(start_iso: str, steps: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    start_ts = pd.Timestamp(start_iso)
    coordinator = MultiAgentCoordinator(CoordinatorConfig(), history=get_history())
    multi_agent = coordinator.run_multi_agent(steps=steps, start=start_ts)
    baseline = coordinator.run_baseline(steps=steps, start=start_ts)
    summary = compare_strategies(multi_agent, baseline)
    log_df = coordinator.get_event_log()
    return multi_agent.reset_index(), baseline.reset_index(), summary, log_df


def chart_line(df: pd.DataFrame, y: str, title: str) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_line()
        .encode(
            x=alt.X("timestamp:T", title="Time"),
            y=alt.Y(f"{y}:Q", title=title),
            color=alt.Color("strategy:N", title="Strategy"),
        )
        .properties(height=250)
    )


def build_dashboard() -> None:
    st.title("Intelligent Flow Optimization – Digital Twin Dashboard")
    history = get_history()

    st.sidebar.header("Scenario")
    sample_times = history.index[::4]
    start_choice = st.sidebar.selectbox(
        "Start timestamp",
        options=sample_times,
        format_func=lambda ts: ts.strftime("%Y-%m-%d %H:%M"),
    )
    remaining_steps = len(history.loc[start_choice:])
    max_hours = max(int(remaining_steps * 0.25), 1)
    default_hours = min(24, max_hours)
    duration_hours = st.sidebar.slider("Duration (hours)", min_value=1, max_value=max_hours, value=default_hours)
    steps = int(duration_hours * 4)

    with st.spinner("Running multi-agent simulation..."):
        multi_df, baseline_df, summary_df, log_df = run_simulation(start_choice.isoformat(), steps)

    for df in (multi_df, baseline_df):
        df["cost_eur"] = (df["energy_kwh"] * df["price_eur_kwh"]).cumsum()
    combined = pd.concat([multi_df.assign(strategy="Multi-Agent"), baseline_df.assign(strategy="Baseline")])

    st.subheader("Key Impact Metrics")
    summary_df = summary_df.copy()
    summary_df.loc[:, "energy_cost_eur"] = summary_df["energy_cost_eur"].round(2)
    metrics_map = summary_df.to_dict("index")
    baseline_cost = float(metrics_map.get("baseline", {}).get("energy_cost_eur", float("nan")))
    multi_cost = float(metrics_map.get("multi_agent", {}).get("energy_cost_eur", float("nan")))
    savings_pct = float("nan")
    if pd.notna(baseline_cost) and baseline_cost > 0 and pd.notna(multi_cost):
        savings_pct = 100.0 * (1 - multi_cost / baseline_cost)
    cols = st.columns(3)
    cols[0].metric("Baseline energy cost (€)", f"{baseline_cost:.2f}" if pd.notna(baseline_cost) else "–")
    cols[1].metric("Multi-agent energy cost (€)", f"{multi_cost:.2f}" if pd.notna(multi_cost) else "–")
    cols[2].metric("Savings vs baseline", f"{savings_pct:.1f}%" if pd.notna(savings_pct) else "–")

    st.subheader("Reservoir Levels vs Safety Bounds")
    level_chart = chart_line(combined, "level_m", "Tunnel level (m)")
    safety_band = alt.Chart(pd.DataFrame({
        "y": [2.0, 6.5],
        "label": ["Min recommended", "Max recommended"],
    })).mark_rule(strokeDash=[4, 4], color="grey").encode(y="y")
    st.altair_chart(level_chart + safety_band, use_container_width=True)

    st.subheader("Inflows, Outflows, and Energy Cost")
    flow_chart = chart_line(combined, "inflow_m3_h", "Flow (m³/h)")
    outflow_chart = chart_line(combined, "outflow_m3_h", "Outflow (m³/h)")
    cost_chart = chart_line(combined, "cost_eur", "Cumulative cost (€)")
    st.altair_chart(flow_chart, use_container_width=True)
    st.altair_chart(outflow_chart, use_container_width=True)
    st.altair_chart(cost_chart, use_container_width=True)

    with st.expander("Detailed logs"):
        st.write("Multi-agent strategy", multi_df.head(20))
        st.write("Baseline strategy", baseline_df.head(20))
        if not log_df.empty:
            st.write("Agent coordination log", log_df.tail(20))


if __name__ == "__main__":
    build_dashboard()
