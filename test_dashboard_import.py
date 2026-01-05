#!/usr/bin/env python3
"""Test dashboard import to diagnose Internal Server Error."""

try:
    from dashboard.app import app
    print("SUCCESS: dashboard.app imported successfully")
    print(f"App type: {type(app)}")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    print("The dashboard.app module is missing or not in Python path")
except Exception as e:
    print(f"OTHER ERROR: {e}")
    import traceback
    traceback.print_exc()
