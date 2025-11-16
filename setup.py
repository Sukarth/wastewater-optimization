"""
Setup Script for Intelligent Wastewater Pumping Optimization
=============================================================

This script helps first-time users set up the project environment.

Usage:
    python setup.py
"""
import subprocess
import sys
from pathlib import Path


def print_banner():
    """Display welcome banner."""
    print("=" * 70)
    print("  INTELLIGENT WASTEWATER PUMPING OPTIMIZATION")
    print("  Junction 2025 | Setup Script")
    print("=" * 70)
    print()


def check_python_version():
    """Verify Python version meets requirements."""
    print("[1/5] Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 13):
        print(f"  [ERROR] Python 3.13+ required. You have {version.major}.{version.minor}.{version.micro}")
        print("  Please upgrade Python: https://www.python.org/downloads/")
        return False
    print(f"  [OK] Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_data_files():
    """Check if required data files exist."""
    print("\n[2/5] Checking data files...")
    data_dir = Path("data")
    required_files = ["Hackathon_HSY_data.xlsx"]
    
    if not data_dir.exists():
        print("  [ERROR] data/ directory not found")
        return False
    
    missing = []
    for file in required_files:
        if not (data_dir / file).exists():
            missing.append(file)
    
    if missing:
        print(f"  [WARNING] Missing data files: {', '.join(missing)}")
        print("  These files are required for simulation.")
        print("  Please add them to the data/ directory.")
        return False
    
    print("  [OK] All required data files found")
    return True


def install_dependencies():
    """Install Python dependencies."""
    print("\n[3/5] Installing dependencies...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT
        )
        print("  [OK] Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [ERROR] Failed to install dependencies: {e}")
        print("  Try manually: pip install -r requirements.txt")
        return False


def verify_imports():
    """Test critical imports."""
    print("\n[4/5] Verifying imports...")
    try:
        import pandas
        import numpy
        import sklearn
        import pulp
        import streamlit
        import altair
        print("  [OK] All core modules imported successfully")
        return True
    except ImportError as e:
        print(f"  [ERROR] Import failed: {e}")
        print("  Run: pip install -r requirements.txt")
        return False


def create_results_directory():
    """Ensure results directory exists."""
    print("\n[5/5] Creating results directory...")
    results_dir = Path("results")
    if not results_dir.exists():
        results_dir.mkdir(parents=True)
        print("  [OK] Created results/ directory")
    else:
        print("  [OK] results/ directory already exists")
    return True


def print_next_steps():
    """Display next steps for user."""
    print("\n" + "=" * 70)
    print("  SETUP COMPLETE!")
    print("=" * 70)
    print("\nNext steps:")
    print("\n1. Run quick demo:")
    print("   python demo.py")
    print("\n2. Launch interactive dashboard:")
    print("   streamlit run dashboard/app.py")
    print("\n3. Run full simulation:")
    print("   python -m src.main")
    print("\n4. Read documentation:")
    print("   README.md")
    print("\n" + "=" * 70)


def main():
    """Run setup process."""
    print_banner()
    
    steps = [
        check_python_version,
        check_data_files,
        install_dependencies,
        verify_imports,
        create_results_directory,
    ]
    
    for step in steps:
        if not step():
            print("\n[FAILED] Setup incomplete. Please fix errors above.")
            sys.exit(1)
    
    print_next_steps()


if __name__ == "__main__":
    main()
