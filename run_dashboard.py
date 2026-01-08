#!/usr/bin/env python3
"""Run the Trader Dashboard."""

import sys

# Add ui_shell to path
sys.path.insert(0, './ui_shell/src')

from ui_shell.dashboard_server import app

if __name__ == '__main__':
    print("Starting Trader Dashboard...")
    print("Visit: http://127.0.0.1:5000")
    print("Make sure market_data server is running on port 8006")
    print("Dashboard auto-refreshes every 30 seconds")
    app.run(host='127.0.0.1', port=5000, debug=False)
