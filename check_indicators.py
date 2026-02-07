#!/usr/bin/env python3
import sys
sys.path.insert(0, 'engine_module/src')
from engine_module.agents.technical_agent import TechnicalIndicatorsService

service = TechnicalIndicatorsService()
indicators = service.get_indicators('BANKNIFTY26JANFUT')
print(f'Indicators available: {list(indicators.keys())}')
if 'rsi_14' in indicators:
    print(f'RSI_14 value: {indicators["rsi_14"]}')
else:
    print('RSI_14 not found')