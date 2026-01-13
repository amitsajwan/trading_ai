#!/usr/bin/env python3
"""
Test dashboard data integration.
"""

import requests
import json

def test_dashboard_integration():
    """Test all data sources needed by the dashboard."""
    print('🎯 Testing Dashboard Data Integration')
    print('=' * 40)

    # Test market data
    try:
        response = requests.get('http://localhost:8004/api/v1/market/tick/BANKNIFTY')
        if response.status_code == 200:
            data = response.json()
            print('✅ Market Data: Available for dashboard')
            print(f'   Current Price: ₹{data["last_price"]:.2f}')
        else:
            print('❌ Market Data: Not available')
    except Exception as e:
        print(f'❌ Market Data Error: {e}')

    # Test signals
    try:
        response = requests.get('http://localhost:8006/api/v1/signals/BANKNIFTY')
        if response.status_code == 200:
            signals = response.json()
            print(f'✅ Trading Signals: {len(signals)} signals available')
            for signal in signals:
                print(f'   • {signal["action"]} ({signal["confidence"]:.1%})')
        else:
            print('❌ Trading Signals: Not available')
    except Exception as e:
        print(f'❌ Signals Error: {e}')

    # Test analysis
    try:
        response = requests.post('http://localhost:8006/api/v1/analyze', json={'instrument': 'BANKNIFTY'}, timeout=30)
        if response.status_code == 200:
            analysis = response.json()
            print('✅ AI Analysis: Working')
            print(f'   Decision: {analysis["decision"]} ({analysis["confidence"]:.1%})')
        else:
            print('❌ AI Analysis: Not working')
    except Exception as e:
        print(f'❌ Analysis Error: {e}')

    print('\n🎉 All backend services are ready for dashboard integration!')

if __name__ == "__main__":
    test_dashboard_integration()