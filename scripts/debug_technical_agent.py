from agents.technical_agent import TechnicalAnalysisAgent
from trading_orchestration.state_manager import StateManager
from data.market_memory import MarketMemory

mm = MarketMemory()
sm = StateManager(mm)
state = sm.initialize_state()
print('OHLC counts:', len(state.ohlc_1min), len(state.ohlc_5min))
tag = TechnicalAnalysisAgent()
try:
    updated = tag.process(state)
    print('technical_analysis:', updated.technical_analysis)
    print('agent_explanations (last):', updated.agent_explanations[-1:] )
except Exception as e:
    print('Exception in tech agent:', e)
