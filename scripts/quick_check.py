"""Backward-compatible quick health check.

Legacy entrypoint: `python scripts/quick_check.py`.
This wrapper invokes `scripts/monitor/verify_all_components.py` which performs a comprehensive system verification.
"""
import sys
from pathlib import Path
import subprocess
import sys

# Run the verification script as a subprocess to preserve output behaviour
verify_path = Path(__file__).parent / 'monitor' / 'verify_all_components.py'
if __name__ == "__main__":
    if not verify_path.exists():
        print("ERROR: verification script not found:", verify_path)
        sys.exit(1)
    try:
        result = subprocess.run([sys.executable, str(verify_path)] + sys.argv[1:])
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n\n⚠️ Verification interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)

