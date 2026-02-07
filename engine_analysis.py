#!/usr/bin/env python3
"""Engine module and orchestrator analysis"""

import requests
import json
import redis

def test_engine_api():
    """Test Engine API health and status"""
    print('ENGINE MODULE ANALYSIS')
    print('=' * 40)

    # Test Engine API health
    try:
        response = requests.get('http://localhost:8006/health', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f'[OK] Engine API Health: {response.status_code}')

            # Check orchestrator status
            orchestrator = data.get('orchestrator', {})
            orchestrator_status = orchestrator.get('status')
            agent_count = orchestrator.get('agent_count', 0)
            mode = orchestrator.get('mode')

            print(f'Orchestrator Status: {orchestrator_status}')
            print(f'Agent Count: {agent_count}')
            print(f'Execution Mode: {mode}')

            # Check data sources
            data_sources = data.get('data_sources', {})
            print(f'Data Sources: {len(data_sources)} configured')

            for source, status in data_sources.items():
                status_icon = '[OK]' if status else '[MISSING]'
                print(f'  {status_icon} {source}')

        else:
            print(f'[FAIL] Engine API: HTTP {response.status_code}')

    except Exception as e:
        print(f'[ERROR] Engine API: {str(e)[:50]}')

    print()

def test_orchestrator_analysis():
    """Test orchestrator analysis capability"""
    print('ORCHESTRATOR ANALYSIS TEST:')
    print('-' * 30)

    try:
        payload = {'instrument': 'BANKNIFTY', 'context': {}}
        response = requests.post('http://localhost:8006/api/v1/analyze',
                               json=payload, timeout=15)

        if response.status_code == 200:
            data = response.json()
            decision = data.get('decision', 'unknown')
            confidence = data.get('confidence', 0)
            agent_responses = data.get('agent_responses', [])

            print(f'[SUCCESS] Analysis completed')
            print(f'Decision: {decision}')
            print(f'Confidence: {confidence:.2f}')
            print(f'Agent Responses: {len(agent_responses)}')

            # Show first few agent responses
            for i, agent in enumerate(agent_responses[:3]):
                agent_name = agent.get('agent', 'unknown')
                agent_decision = agent.get('decision', 'unknown')
                print(f'  Agent {i+1}: {agent_name} - {agent_decision}')

        else:
            print(f'[FAIL] Analysis failed: HTTP {response.status_code}')
            print(response.text[:200])

    except Exception as e:
        print(f'[ERROR] Analysis failed: {str(e)[:50]}')

    print()

def check_redis_data():
    """Check Redis for orchestrator and engine data"""
    print('REDIS ORCHESTRATOR DATA:')
    print('-' * 25)

    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)

        # Check execution mode
        mode = r.get('system:execution_mode')
        run_id = r.get('system:run_id')

        print(f'System Mode: {mode or "Not set"}')
        print(f'Run ID: {run_id or "Not set"}')

        # Check for agent status
        agent_keys = r.keys('agent:*:status')
        print(f'Active Agents: {len(agent_keys)}')

        # Check for signals
        signal_keys = r.keys('signal:*')
        print(f'Active Signals: {len(signal_keys)}')

        # Check for decisions
        decision_keys = r.keys('decision:*')
        print(f'Active Decisions: {len(decision_keys)}')

        # Check market data availability
        price = r.get('price:BANKNIFTY:latest')
        indicators = len(r.keys('indicators:BANKNIFTY:*'))

        print(f'Latest Price: {price}')
        print(f'Indicators Available: {indicators}')

    except Exception as e:
        print(f'[ERROR] Redis check: {str(e)[:50]}')

def analyze_data_flow():
    """Analyze what data the orchestrator needs vs what's available"""
    print('\nORCHESTRATOR DATA FLOW ANALYSIS:')
    print('-' * 35)

    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)

        # Required data sources for orchestrator
        required_data = {
            'Market Data': bool(r.get('price:BANKNIFTY:latest')),
            'Technical Indicators': len(r.keys('indicators:BANKNIFTY:*')) > 0,
            'OHLC Data': len(r.keys('ohlc:BANKNIFTY:*')) > 0,
            'System Mode': bool(r.get('system:execution_mode')),
            'Agent Status': len(r.keys('agent:*:status')) > 0,
        }

        all_available = True
        for data_type, available in required_data.items():
            status = '[OK]' if available else '[MISSING]'
            print(f'{status} {data_type}: {available}')
            if not available:
                all_available = False

        print()
        if all_available:
            print('[SUCCESS] All required data sources available for orchestrator')
        else:
            print('[WARNING] Some data sources missing - orchestrator may not work properly')

    except Exception as e:
        print(f'[ERROR] Data flow analysis: {str(e)[:50]}')

if __name__ == '__main__':
    test_engine_api()
    test_orchestrator_analysis()
    check_redis_data()
    analyze_data_flow()

    print('\n' + '=' * 60)
    print('ANALYSIS COMPLETE')
    print('If orchestrator is not working, check data sources above.')
    print('=' * 60)