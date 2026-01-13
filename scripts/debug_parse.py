import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine_module.signal_creator import extract_conditions_from_reasoning, create_signals_from_decision
from engine_module.contracts import AnalysisResult

r = "RSI > 30 and volume > 100000"
print('extract:', extract_conditions_from_reasoning(r))
print('\n--- function source (first 400 lines) ---')
import inspect
src = inspect.getsource(create_signals_from_decision)
print('\n'.join(src.splitlines()[:400]))
print('\n--- run function result ---')
print('signals:', create_signals_from_decision(AnalysisResult(decision='BUY', confidence=0.7, details={'reasoning': r}), 'BANKNIFTY', current_price=45000.0))
