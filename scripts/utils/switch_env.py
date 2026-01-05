"""Switch environment configuration for different instruments."""

import os
import sys
import shutil
from pathlib import Path

# Available instrument configurations
AVAILABLE_CONFIGS = {
    "btc": ".env.btc",
    "banknifty": ".env.banknifty",
    "nifty": ".env.nifty"
}

def switch_env(instrument: str):
    """Switch to the specified instrument configuration."""
    instrument = instrument.lower()

    if instrument not in AVAILABLE_CONFIGS:
        print(f"ERROR: Invalid instrument: {instrument}")
        print(f"Available options: {', '.join(AVAILABLE_CONFIGS.keys())}")
        return False

    env_file = Path(".env")
    source_file = Path(AVAILABLE_CONFIGS[instrument])

    if not source_file.exists():
        print(f"ERROR: Configuration file {source_file} not found")
        return False

    # Backup current .env if it exists
    if env_file.exists():
        backup_file = Path(".env.backup")
        shutil.copy2(env_file, backup_file)
        print(f"Backed up current .env to {backup_file}")

    # Copy the new configuration
    shutil.copy2(source_file, env_file)
    print(f"Switched to {instrument.upper()} configuration")
    print(f"Copied {source_file} to {env_file}")
    print("\nRestart the system to use the new configuration.")

    return True

def main():
    if len(sys.argv) != 2:
        print("Usage: python switch_env.py <instrument>")
        print(f"Available instruments: {', '.join(AVAILABLE_CONFIGS.keys())}")
        return

    instrument = sys.argv[1]
    success = switch_env(instrument)

    if success:
        print("\nTo apply changes:")
        print("1. Restart any running services")
        print("2. Run: docker compose restart backend")
        print("3. Or restart the application")

if __name__ == "__main__":
    main()