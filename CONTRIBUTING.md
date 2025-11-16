# Contributing to Intelligent Wastewater Pumping Optimization

Thank you for your interest in contributing! This project was developed for Junction 2025 hackathon, and we welcome improvements and extensions.

## 🚀 Getting Started

### Prerequisites
- Python 3.13+
- Git
- Basic understanding of optimization and control systems

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/sukarth/wastewater-optimization.git
   cd wastewater-optimization
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify Installation**
   ```bash
   python demo.py
   ```

## 🔧 Making Changes

### Branch Naming
- `feature/` - New features (e.g., `feature/weather-integration`)
- `bugfix/` - Bug fixes (e.g., `bugfix/forecast-nan-handling`)
- `docs/` - Documentation updates (e.g., `docs/api-reference`)
- `refactor/` - Code improvements (e.g., `refactor/planner-optimization`)

### Code Style
- **PEP 8**: Follow Python style guide
- **Type Hints**: Use for all function signatures
- **Docstrings**: Required for public functions/classes
- **Line Length**: Max 100 characters (120 acceptable for long strings)

**Example:**
```python
def calculate_pump_energy(
    flow_m3_per_h: float,
    head_m: float,
    efficiency: float,
    dt_hours: float = 0.25
) -> float:
    """Calculate energy consumption for a pump operation.
    
    Args:
        flow_m3_per_h: Volumetric flow rate (m³/h)
        head_m: Hydraulic head (meters)
        efficiency: Pump efficiency (0-1)
        dt_hours: Time duration (hours)
    
    Returns:
        Energy consumed (kWh)
    """
    # Implementation...
```

### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Formatting, no code change
- `refactor:` - Code restructuring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

**Examples:**
```
feat: add weather forecast integration for inflow prediction
fix: handle NaN values in forecaster agent
docs: update installation instructions for Linux
refactor: optimize LP formulation in planner agent
```

## 🧪 Testing

### Running Tests
```bash
# Unit tests (when implemented)
pytest tests/

# Demo simulation
python demo.py

# Dashboard
streamlit run dashboard/app.py
```

### Adding Tests
Place test files in `tests/` directory:
```
tests/
├── test_agents.py
├── test_simulation.py
└── test_utils.py
```

## 📝 Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/my-awesome-feature
   ```

2. **Make Your Changes**
   - Write code
   - Add/update tests
   - Update documentation

3. **Test Locally**
   ```bash
   python demo.py  # Should complete without errors
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add my awesome feature"
   ```

5. **Push to Your Fork**
   ```bash
   git push origin feature/my-awesome-feature
   ```

6. **Create Pull Request**
   - Go to GitHub
   - Click "New Pull Request"
   - Fill out template (see below)
   - Link related issues

### PR Template
```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Changes Made
- Change 1
- Change 2

## Testing
How was this tested?

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented if necessary)
```

## 🎯 Areas for Contribution

### High Priority
- [ ] Weather data integration (rainfall → inflow prediction)
- [ ] LSTM/Transformer forecasting models
- [ ] Real-time dashboard updates (WebSocket)
- [ ] Unit test suite
- [ ] Performance benchmarking tools

### Medium Priority
- [ ] Reinforcement learning agent
- [ ] Multi-objective optimization (cost + emissions)
- [ ] Predictive maintenance alerts
- [ ] Cloud deployment scripts (Azure/AWS)
- [ ] Mobile app prototype

### Good First Issues
- [ ] Add more pump models to `src/utils/pumps.py`
- [ ] Improve error messages
- [ ] Add input validation
- [ ] Write API documentation
- [ ] Create tutorial notebooks

## 🐛 Reporting Bugs

### Before Submitting
1. Check existing issues
2. Try latest version
3. Verify it's reproducible

### Bug Report Template
```markdown
**Environment:**
- OS: [e.g., Windows 11]
- Python: [e.g., 3.13.0]
- Dependencies: [paste `pip freeze` output]

**Description:**
Clear description of the bug

**Steps to Reproduce:**
1. Step 1
2. Step 2
3. ...

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Logs/Screenshots:**
Paste relevant output
```

## 💡 Feature Requests

We welcome new ideas! Please open an issue with:
- **Problem**: What problem does this solve?
- **Proposed Solution**: How would it work?
- **Alternatives**: Other options considered
- **Context**: Use cases, mockups, etc.

## 📜 Code of Conduct

### Our Standards
- Be respectful and inclusive
- Accept constructive criticism
- Focus on what's best for the project
- Show empathy toward others

### Unacceptable Behavior
- Harassment or discrimination
- Trolling or insulting comments
- Personal or political attacks
- Publishing private information

## 📧 Contact

- **Issues**: Use GitHub Issues for bugs/features
- **Discussions**: Use GitHub Discussions for questions
- **Email**: [your email] for security concerns

## 🙏 Recognition

Contributors will be recognized in:
- README.md acknowledgments
- Release notes
- Project documentation

Thank you for making this project better! 🌊
