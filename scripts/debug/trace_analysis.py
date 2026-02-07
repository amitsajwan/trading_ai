#!/usr/bin/env python3
"""
Detailed system trace analysis showing data flow through all components.
"""

import requests
import json
import time

def trace_system_flow():
    """Trace data flow through the entire system."""
    print('🔍 DETAILED SYSTEM TRACE ANALYSIS')
    print('=' * 50)

    # 1. Check market data
    print('1. 📊 Fetching current market data...')
    response = requests.get('http://localhost:8004/api/v1/market/tick/BANKNIFTY')
    tick_data = response.json()
    print(f'   Current price: ₹{tick_data["last_price"]:.2f} at {tick_data["timestamp"]}')

    # 2. Run technical analysis
    print('\n2. 🔧 Fetching technical indicators...')
    response = requests.get('http://localhost:8004/api/v1/technical/indicators/BANKNIFTY?timeframe=minute')
    if response.status_code == 200:
        indicators = response.json()
        rsi = indicators.get("rsi_14", "N/A")
        macd = indicators.get("macd_value", "N/A")
        bb_upper = indicators.get("bollinger_upper", "N/A")
        print(f'   RSI(14): {rsi if rsi != "N/A" else "N/A"}')
        print(f'   MACD: {macd if macd != "N/A" else "N/A"}')
        print(f'   Bollinger Upper: {bb_upper if bb_upper != "N/A" else "N/A"}')
    else:
        print(f'   Technical indicators unavailable: {response.status_code}')

    # 3. Run engine analysis
    print('\n3. 🤖 Running AI agent analysis...')
    start_time = time.time()
    response = requests.post('http://localhost:8006/api/v1/analyze', json={'instrument': 'BANKNIFTY'}, timeout=60)
    analysis_time = time.time() - start_time

    if response.status_code == 200:
        analysis = response.json()
        print(f'   Analysis completed in {analysis_time:.1f}s')
        print(f'   Decision: {analysis["decision"]} ({analysis["confidence"]:.1%})')

        details = analysis['details']
        agg = details['aggregated_analysis']
        breakdown = agg['agent_breakdown']
        print(f'   Agent votes: BUY:{breakdown["buy_signals"]} SELL:{breakdown["sell_signals"]} HOLD:{breakdown["hold_signals"]}')

        if 'key_insights' in agg:
            print('   Key insights:')
            for insight in agg['key_insights'][:2]:
                print(f'     • {insight}')
    else:
        print(f'   Analysis failed: {response.status_code}')

    # 4. Check signal status
    print('\n4. 🎯 Checking signal monitoring...')
    response = requests.get('http://localhost:8006/api/v1/signals/BANKNIFTY')
    if response.status_code == 200:
        signals = response.json()
        print(f'   Active signals: {len(signals)}')
        for signal in signals:
            print(f'     • {signal["action"]} (confidence: {signal["confidence"]:.1%}, status: {signal["status"]})')

    print('\n✅ System trace analysis completed')

if __name__ == "__main__":
    trace_system_flow()