"""Unified processor service.

Mode-agnostic processing entrypoint. Currently runs the volume enhancer (LTP processor)
if enabled via environment.
"""
from __future__ import annotations

import os
import time

from market_data.processors.volume_enhancer import run_volume_enhancer


def main() -> None:
    enable_ltp = os.getenv("ENABLE_LTP_PROCESSOR", "1").lower() in ("1", "true", "yes")

    if enable_ltp:
        run_volume_enhancer(market_memory=None)
        return

    print("[market_data] Unified processor idle (no processors enabled)")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
