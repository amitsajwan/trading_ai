#!/usr/bin/env python3
"""
Analyze the current analysis response structure.
"""

import requests
import json

def analyze_response():
    """Analyze the analysis response structure."""
    print('📊 Current Analysis Response Structure')
    print('=' * 45)

    # Get current analysis response
    response = requests.post('http://localhost:8006/api/v1/analyze', json={'instrument': 'BANKNIFTY'}, timeout=30)
    if response.status_code == 200:
        data = response.json()
        details = data['details']
        agg = details['aggregated_analysis']

        print('Available data sections:')
        for key in agg.keys():
            if key.endswith('_signals'):
                signals = agg[key]
                print(f'  • {key}: {len(signals)} items')
                if signals:
                    sample = signals[0]
                    print(f'    Sample keys: {list(sample.keys())}')
            else:
                print(f'  • {key}: {type(agg[key])}')

        # Check what reasoning/details are available
        print('\nReasoning/Details available:')
        for signal_type in ['technical_signals', 'sentiment_signals', 'macro_signals']:
            if signal_type in agg:
                for signal in agg[signal_type][:1]:  # Just first one
                    print(f'  {signal_type} sample:')
                    for key, value in signal.items():
                        if key == 'indicators' and isinstance(value, dict):
                            print(f'    {key}: {len(value)} indicator fields')
                        elif len(str(value)) < 50:
                            print(f'    {key}: {value}')
                        else:
                            print(f'    {key}: {str(value)[:50]}...')

        # Show what dashboard could display
        print('\n🎯 Dashboard Enhancement Opportunities:')
        print('  ✅ Already showing: Agent decisions, confidence levels')
        print('  🔄 Could add: Detailed reasoning per agent')
        print('  🔄 Could add: Technical indicator values')
        print('  🔄 Could add: Agent-specific insights')
        print('  🔄 Could add: Historical performance')

    else:
        print(f'❌ API call failed: {response.status_code}')

if __name__ == "__main__":
    analyze_response()