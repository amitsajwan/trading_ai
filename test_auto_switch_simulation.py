#!/usr/bin/env python3
"""Test auto-switch behavior by simulating different market hours."""

import sys
import os
from datetime import datetime, time
from unittest.mock import patch

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from core_kernel.src.core_kernel.mode_manager import ModeManager
from core_kernel.src.core_kernel.market_hours import is_market_open, get_suggested_mode


def test_auto_switch_scenarios():
    """Test auto-switch in different scenarios."""
    print("=" * 60)
    print("Testing Auto-Switch Scenarios")
    print("=" * 60)
    print()
    
    # Scenario 1: Market opens (should switch from mock to live)
    print("Scenario 1: Market Opens (Mock -> Live)")
    print("-" * 60)
    
    manager = ModeManager()
    manager.clear_manual_override()  # Clear any override
    
    # Simulate market closed (current state)
    with patch('core_kernel.src.core_kernel.market_hours.is_market_open', return_value=False):
        with patch('core_kernel.src.core_kernel.market_hours.get_suggested_mode', return_value='paper_mock'):
            manager._current_mode = 'paper_mock'
            should_switch, suggested, reason = manager.check_auto_switch()
            print(f"  Current mode: {manager._current_mode}")
            print(f"  Market open: False")
            print(f"  Should switch: {should_switch}")
            print(f"  Suggested: {suggested}")
            print()
    
    # Simulate market opens
    with patch('core_kernel.src.core_kernel.market_hours.is_market_open', return_value=True):
        with patch('core_kernel.src.core_kernel.market_hours.get_suggested_mode', return_value='paper_live'):
            should_switch, suggested, reason = manager.check_auto_switch()
            print(f"  Market open: True")
            print(f"  Should switch: {should_switch}")
            print(f"  Suggested: {suggested}")
            print(f"  Reason: {reason}")
            
            if should_switch and suggested == 'paper_live':
                switched, new_mode, confirmation = manager.auto_switch(require_confirmation_for_live=True)
                if switched:
                    print(f"  [OK] Auto-switched to: {new_mode}")
                else:
                    print(f"  [FAIL] Auto-switch failed")
            print()
    
    # Scenario 2: Market closes (should switch from live to mock)
    print("Scenario 2: Market Closes (Live -> Mock)")
    print("-" * 60)
    
    manager._current_mode = 'paper_live'
    manager.clear_manual_override()
    
    with patch('core_kernel.src.core_kernel.market_hours.is_market_open', return_value=False):
        with patch('core_kernel.src.core_kernel.market_hours.get_suggested_mode', return_value='paper_mock'):
            should_switch, suggested, reason = manager.check_auto_switch()
            print(f"  Current mode: {manager._current_mode}")
            print(f"  Market open: False")
            print(f"  Should switch: {should_switch}")
            print(f"  Suggested: {suggested}")
            print(f"  Reason: {reason}")
            
            if should_switch and suggested == 'paper_mock':
                switched, new_mode, confirmation = manager.auto_switch(require_confirmation_for_live=True)
                if switched:
                    print(f"  [OK] Auto-switched to: {new_mode}")
                else:
                    print(f"  [FAIL] Auto-switch failed")
            print()
    
    # Scenario 3: Manual override prevents auto-switch
    print("Scenario 3: Manual Override Prevents Auto-Switch")
    print("-" * 60)
    
    manager.set_manual_mode('paper_mock', require_confirmation=False)
    
    with patch('core_kernel.src.core_kernel.market_hours.is_market_open', return_value=True):
        with patch('core_kernel.src.core_kernel.market_hours.get_suggested_mode', return_value='paper_live'):
            should_switch, suggested, reason = manager.check_auto_switch()
            print(f"  Current mode: {manager._current_mode}")
            print(f"  Has manual override: {manager.has_manual_override()}")
            print(f"  Market open: True")
            print(f"  Should switch: {should_switch}")
            print(f"  Reason: {reason}")
            
            if not should_switch and 'Manual override' in reason:
                print(f"  [OK] Manual override correctly prevents auto-switch")
            else:
                print(f"  [FAIL] Manual override not working correctly")
            print()
    
    # Scenario 4: Live mode requires confirmation
    print("Scenario 4: Live Mode Requires Confirmation")
    print("-" * 60)
    
    manager.clear_manual_override()
    manager._current_mode = 'paper_mock'
    
    # Simulate trying to switch to live mode
    success, message = manager.set_manual_mode('live', require_confirmation=True)
    print(f"  Attempting to set live mode (require_confirmation=True)")
    print(f"  Success: {success}")
    print(f"  Message: {message}")
    
    if not success and message == "CONFIRMATION_REQUIRED":
        print(f"  [OK] Live mode correctly requires confirmation")
    else:
        print(f"  [FAIL] Live mode confirmation not working")
    print()
    
    # Test with confirmation
    success, message = manager.set_manual_mode('live', require_confirmation=False)
    print(f"  Setting live mode (require_confirmation=False)")
    print(f"  Success: {success}")
    print(f"  Message: {message}")
    
    if success:
        print(f"  [OK] Live mode set with confirmation")
    else:
        print(f"  [FAIL] Live mode setting failed")
    print()
    
    print("=" * 60)
    print("Auto-Switch Simulation Complete")
    print("=" * 60)


if __name__ == "__main__":
    test_auto_switch_scenarios()


