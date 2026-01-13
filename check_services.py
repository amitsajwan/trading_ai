#!/usr/bin/env python3
"""Check if all trading system services are running."""

import requests
import socket

def check_service(name, host, port, path="/"):
    """Check if a service is running."""
    try:
        # Check port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((host, port))
        sock.close()

        if result != 0:
            return f"❌ {name}: Port {port} closed"

        # Check HTTP endpoint
        try:
            url = f"http://{host}:{port}{path}"
            response = requests.get(url, timeout=5)
            return f"✅ {name}: {response.status_code}"
        except:
            return f"⚠️ {name}: Port open but HTTP failed"

    except Exception as e:
        return f"❌ {name}: Error - {e}"

def main():
    print("🔍 Checking Trading System Services")
    print("=" * 40)

    services = [
        ("Dashboard UI", "localhost", 8888, "/"),
        ("Engine API", "localhost", 8006, "/health"),
        ("Market Data API", "localhost", 8004, "/health"),
        ("WebSocket Gateway", "localhost", 8889, "/health"),
        ("Redis", "localhost", 6379, None),  # Redis doesn't have HTTP
    ]

    for name, host, port, path in services:
        if port == 6379:  # Redis check
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((host, port))
            sock.close()
            status = "✅ Redis: Connected" if result == 0 else "❌ Redis: Not connected"
        else:
            status = check_service(name, host, port, path)
        print(status)

    print("\n📝 Service Status Summary")
    print("- Dashboard UI (port 8888): Frontend interface")
    print("- Engine API (port 8006): AI analysis and orchestrator")
    print("- Market Data API (port 8004): Real-time market data")
    print("- WebSocket Gateway (port 8889): Real-time data streaming")
    print("- Redis (port 6379): Data cache and pub/sub")

if __name__ == "__main__":
    main()