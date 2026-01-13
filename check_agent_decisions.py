#!/usr/bin/env python3
"""
Check what individual agents are deciding.
"""

import requests
import json

def check_agent_decisions():
    """Check individual agent decisions."""
    print('🔍 Checking Individual Agent Decisions')
    print('=' * 45)

    # Run analysis and check agent details
    response = requests.post('http://localhost:8006/api/v1/analyze', json={'instrument': 'BANKNIFTY'}, timeout=30)
    if response.status_code == 200:
        data = response.json()
        print(f'Overall Decision: {data["decision"]} ({data["confidence"]:.1%})')

        details = data['details']
        agg = details['aggregated_analysis']

        print('\nIndividual Agent Decisions:')
        technical = agg.get('technical_signals', [])
        for agent in technical:
            name = agent['agent'].replace('Agent', '')
            decision = agent['signal']
            confidence = agent['confidence']
            print(f'  {name}: {decision} ({confidence:.1%})')

        # Check if any agent has BUY/SELL
        has_actionable = any(agent['signal'] not in ['HOLD', 'ERROR'] for agent in technical)
        print(f'\nActionable signals found: {has_actionable}')

        if not has_actionable:
            print('❌ All agents returning HOLD - no signals will be created')
            print('💡 Need agents to generate BUY/SELL decisions for signals')
        else:
            print('✅ Actionable signals detected - signals should be created')

    else:
        print(f'❌ Analysis failed: {response.status_code}')

if __name__ == "__main__":
    check_agent_decisions()