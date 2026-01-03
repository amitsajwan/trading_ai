"""Setup virtual environment and install dependencies."""

import subprocess
import sys
import os
from pathlib import Path

def setup_venv():
    """Create and setup virtual environment."""
    venv_path = Path(".venv")
    
    print("=" * 70)
    print("Setting up Virtual Environment")
    print("=" * 70)
    
    # Create venv if it doesn't exist
    if not venv_path.exists():
        print("Creating virtual environment (.venv)...")
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
        print("SUCCESS: Virtual environment created")
    else:
        print("SUCCESS: Virtual environment already exists")
    
    # Determine pip path based on OS
    if sys.platform == "win32":
        pip_path = venv_path / "Scripts" / "pip.exe"
        python_path = venv_path / "Scripts" / "python.exe"
    else:
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"
    
    # Upgrade pip
    print("\nUpgrading pip...")
    subprocess.run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    print("SUCCESS: pip upgraded")
    
    # Install requirements
    requirements_file = Path("requirements.txt")
    if requirements_file.exists():
        print("\nInstalling requirements...")
        subprocess.run([str(pip_path), "install", "-r", str(requirements_file)], check=True)
        print("SUCCESS: Requirements installed")
    else:
        print("WARNING: requirements.txt not found")
    
    print("\n" + "=" * 70)
    print("Virtual environment setup complete!")
    print("=" * 70)
    print("\nTo activate:")
    if sys.platform == "win32":
        print("  .venv\\Scripts\\activate")
    else:
        print("  source .venv/bin/activate")
    print("\nOr use the start scripts which auto-activate:")
    print("  python scripts/start_all.py BTC")
    print("  python scripts/start_all.py BANKNIFTY")
    print("  python scripts/start_all.py NIFTY")
    print("=" * 70)

if __name__ == "__main__":
    setup_venv()

