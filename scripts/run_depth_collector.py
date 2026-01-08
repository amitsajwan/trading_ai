"""Thin wrapper to run depth collector from scripts directory.

Used by docker-compose for compatibility with existing structure.
"""
import sys
from pathlib import Path

# Add market_data to path
module_root = Path(__file__).resolve().parents[1] / "market_data" / "src"
if str(module_root) not in sys.path:
    sys.path.insert(0, str(module_root))

from market_data.collectors.depth_collector import main

if __name__ == "__main__":
    main()

