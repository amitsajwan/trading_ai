"""Backward-compatible wrapper for configure_instrument.

Legacy entrypoint: `python scripts/configure_instrument.py <INSTRUMENT>`
This wrapper delegates to `scripts/utils/configure_instrument.py`.
"""
import sys
import subprocess
from pathlib import Path

# Run the real utils/configure_instrument.py via subprocess for robust behavior
target = Path(__file__).parent / 'utils' / 'configure_instrument.py'
if __name__ == "__main__":
    if not target.exists():
        print(f"ERROR: target configure script not found: {target}")
        sys.exit(1)
    try:
        # Pass through any args (e.g., instrument name)
        result = subprocess.run([sys.executable, str(target)] + sys.argv[1:])
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n\n⚠️ Configure interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"ERROR running configure_instrument: {e}")
        sys.exit(1)
