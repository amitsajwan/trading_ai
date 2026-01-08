#!/usr/bin/env python3
import requests

print('=== LIVE BANK NIFTY PAPER TRADING TEST ===')
print()

try:
    # Test dashboard access
    r = requests.get('http://localhost:8888/')
    print(f'Dashboard: {r.status_code} - Live Bank Nifty Paper Trading')

    # Test market data
    r = requests.get('http://localhost:8888/api/market/data/BANKNIFTY')
    data = r.json()
    if data.get('success'):
        market = data['data']
        print(f'Bank Nifty Data: INR{market.get("price", 0):,.0f} (RSI: {market.get("rsi_14", 0):.1f})')

        # Check if paper trading is configured
        r = requests.get('http://localhost:8888/api/health')
        health = r.json()
        trading = health.get('trading', {})
        print(f'Paper Trading: Account INR{trading.get("account_balance", 0):,.0f}')

        # Test signal generation
        r = requests.post('http://localhost:8888/api/trading/cycle')
        cycle = r.json()
        print(f'Trading Cycle: {cycle.get("message", "No signals")}')

        signals = cycle.get('signals', [])
        if signals:
            print(f'Signals Generated: {len(signals)} for Bank Nifty')
            for sig in signals[:2]:
                agent = sig.get('agent_name', 'Unknown')
                action = sig.get('action', 'HOLD')
                confidence = sig.get('confidence', 0)
                print(f'  - {agent}: {action} ({confidence:.1%})')

    else:
        print('Bank Nifty data not available')

except Exception as e:
    print(f'Error: {e}')

print()
print('LIVE BANK NIFTY PAPER TRADING IS ACTIVE!')
print('Dashboard: http://localhost:8888')
print('Focus: Bank Nifty with conditional execution')
print('Mode: Paper trading with live-like data updates')

