# Quick Reference Guide

**Intelligent Wastewater Pumping Optimization - Cheat Sheet**

---

## 📦 Installation

```bash
# Clone repository
git clone https://github.com/sukarth/wastewater-optimization.git
cd wastewater-optimization

# Setup environment
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Verify setup
python setup.py
```

---

## 🚀 Running the Project

### Quick Demo (Recommended First Run)
```bash
python demo.py
```
**Output**: 24-hour simulation results with cost comparison

### Interactive Dashboard
```bash
streamlit run dashboard/app.py
```
**Access**: http://localhost:8501

### Full Simulation with Logging
```bash
python -m src.main
```
**Output**: Detailed CSV files in `results/` directory

---

## 🔧 Common Commands

### Python Environment
```bash
# Activate virtual environment
.venv\Scripts\activate           # Windows
source .venv/bin/activate        # Linux/Mac

# Deactivate
deactivate

# Update dependencies
pip install -r requirements.txt --upgrade

# Check installed packages
pip freeze
```

### Data Inspection
```bash
# Open Excel file (if installed)
start data/Hackathon_HSY_data.xlsx  # Windows
open data/Hackathon_HSY_data.xlsx   # Mac
```

### Results Analysis
```bash
# View CSV results
python -c "import pandas as pd; print(pd.read_csv('results/improved_multi_agent.csv').head())"

# Compare strategies
python -c "import pandas as pd; ma=pd.read_csv('results/improved_multi_agent.csv'); bl=pd.read_csv('results/improved_baseline.csv'); print(f'MA Cost: {(ma.energy_kwh*ma.price_eur_kwh).sum():.2f}'); print(f'BL Cost: {(bl.energy_kwh*bl.price_eur_kwh).sum():.2f}')"
```

---

## 📊 Key Metrics

| Metric | Description | Good Range |
|--------|-------------|------------|
| **Cost Savings** | % reduction vs baseline | >20% |
| **Tunnel Level** | Average water height | 1.0-3.0 m |
| **Energy Usage** | Total kWh consumed | Minimize |
| **Constraint Violations** | Safety breaches | 0 (strict) |

---

## 🛠️ Configuration

### Modify Simulation Parameters
Edit `src/agents/coordinator.py`:
```python
config = CoordinatorConfig(
    steps=96,                 # 24 hours (15-min timesteps)
    start_time="2024-11-15",  # Start date
    forecaster_horizon=8,     # 2-hour forecast
    planner_horizon=8,        # 2-hour planning
)
```

### Adjust Optimization Weights
Edit `src/agents/planner.py`:
```python
config = PlannerConfig(
    volume_penalty_weight=60.0,      # Prefer maintaining volume
    operational_min_level_m=1.2,     # Soft minimum level
    target_level_m=3.8,              # Ideal operating level
)
```

### Modify Safety Constraints
Edit `src/agents/safety.py`:
```python
config = SafetyConfig(
    min_level_m=0.5,                 # Hard minimum
    max_level_m=7.5,                 # Hard maximum
    max_total_flow_m3_per_h=16000,   # Total pump capacity
)
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `demo.py` | Quick command-line demo |
| `dashboard/app.py` | Streamlit web interface |
| `src/agents/coordinator.py` | Multi-agent orchestrator |
| `src/agents/planner.py` | LP optimization |
| `src/agents/forecast.py` | ML prediction |
| `src/agents/safety.py` | Constraint enforcement |
| `src/simulation/environment.py` | Digital twin |
| `requirements.txt` | Python dependencies |

---

## 🐛 Troubleshooting

### "No module named 'sklearn'"
```bash
pip install scikit-learn
```

### "File not found: Hackathon_HSY_data.xlsx"
Ensure data file is in `data/` directory.

### "LP solver not found"
```bash
pip install pulp
# Or install CBC solver separately
```

### Dashboard won't start
```bash
pip install streamlit altair --upgrade
streamlit run dashboard/app.py
```

### Encoding errors on Windows
```bash
# Set UTF-8 encoding
chcp 65001
python demo.py
```

---

## 📈 Interpreting Results

### Cost Savings >25%
✅ **Excellent** - System effectively exploits price arbitrage

### Cost Savings 10-25%
✅ **Good** - Reasonable optimization in stable price scenario

### Cost Savings <10%
⚠️ **Acceptable** - Low price volatility limits savings potential

### Energy Increase <10%
✅ **Normal** - Cost optimization may increase cycles for better timing

### Energy Increase >10%
⚠️ **Review** - Check if operational constraints are too tight

### Level Higher than Baseline
✅ **Good** - Strategic storage reduces pump head and wear

---

## 🔗 Quick Links

- 📖 [Full README](README.md)
- 🤝 [Contributing Guide](CONTRIBUTING.md)
- 📜 [Changelog](CHANGELOG.md)
- 📄 [License](LICENSE)
- 🐛 [Report Issue](https://github.com/sukarth/wastewater-optimization/issues)

---

## 💡 Tips

1. **First run**: Always run `python demo.py` to verify setup
2. **Data exploration**: Use dashboard to understand agent decisions
3. **Tuning**: Start with default configs, adjust based on results
4. **Performance**: 24-hour simulation takes ~30 seconds
5. **Learning**: Read agent logs to understand optimization strategy

---

**Need Help?** Check README.md or open an issue on GitHub.
