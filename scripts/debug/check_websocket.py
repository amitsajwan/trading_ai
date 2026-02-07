#!/usr/bin/env python3
"""
Check WebSocket gateway status.
"""

import subprocess
import socket

def check_websocket_gateway():
    """Check if WebSocket gateway is running."""
    print('🔍 Checking WebSocket Gateway Status')
    print('=' * 40)

    # Check if port 8889 is open
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8889))
        sock.close()

        if result == 0:
            print('✅ Port 8889 is OPEN - WebSocket gateway appears to be running')
        else:
            print('❌ Port 8889 is CLOSED - WebSocket gateway is NOT running')
            print('   This explains why the dashboard cannot connect')
    except Exception as e:
        print(f'❌ Error checking port 8889: {e}')

    # Check running processes
    print('\n🔍 Checking running Python processes...')
    try:
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], capture_output=True, text=True)
        python_processes = [line for line in result.stdout.split('\n') if 'python.exe' in line]
        print(f'Found {len(python_processes)} Python processes running')
        for proc in python_processes[:5]:  # Show first 5
            if proc.strip():
                print(f'   {proc.strip()}')
    except Exception as e:
        print(f'❌ Error checking processes: {e}')

    print('\n💡 Solution: Start the WebSocket gateway')
    print('   The redis_ws_gateway module needs to be running on port 8889')

if __name__ == "__main__":
    check_websocket_gateway()