#!/usr/bin/env python3
"""Quick verification of current system state."""

import sys
import os
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(__file__))

from core_kernel.src.core_kernel.market_hours import is_market_open, get_market_status, get_suggested_mode
from core_kernel.src.core_kernel.mode_manager import get_mode_manager
from core_kernel.src.core_kernel.mongodb_schema import get_db_for_mode, get_db_connection

print("=" * 60)
print("CURRENT SYSTEM STATE")
print("=" * 60)
print()

now = datetime.now()
market_open, status = get_market_status(now)
suggested = get_suggested_mode(now)

print(f"Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Market Status: {status}")
print(f"Market Open: {market_open}")
print(f"Suggested Mode: {suggested}")
print()

manager = get_mode_manager()
mode_info = manager.get_mode_info()

print(f"Current Mode: {mode_info['current_mode']}")
print(f"Database: {get_db_for_mode(mode_info['current_mode'])}")
print(f"Has Manual Override: {mode_info['has_manual_override']}")
if mode_info['has_manual_override']:
    print(f"Manual Override: {mode_info['manual_override']}")
print()

should_switch = mode_info['should_auto_switch']
if should_switch:
    print(f"[WARN] Auto-switch recommended:")
    print(f"  Current: {mode_info['current_mode']}")
    print(f"  Suggested: {mode_info['auto_switch_suggested']}")
    print(f"  Reason: {mode_info['auto_switch_reason']}")
else:
    print("[OK] No auto-switch needed")
    print(f"  Reason: {mode_info['auto_switch_reason']}")

print()
print("=" * 60)


