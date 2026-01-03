from trading_orchestration.trading_graph import TradingGraph
from data.market_memory import MarketMemory

mm = MarketMemory()
trading_graph = TradingGraph(market_memory=mm)
res = trading_graph.run()
print('result type:', type(res))
# Inspect attributes on the returned object
try:
    print('dir:', [d for d in dir(res) if not d.startswith('_')][:40])
except Exception as e:
    print('dir failed:', e)
# Try to convert via model_dump/dict/to_dict
for attr in ('model_dump','dict','to_dict','toJSON'):
    if hasattr(res, attr):
        try:
            print(f"{attr}() -> keys:", list(getattr(res,attr)().keys())[:10])
        except Exception as e:
            print(f"{attr}() failed: {e}")
# Try attribute access for known fields
for f in ['technical_analysis','fundamental_analysis','sentiment_analysis','macro_analysis','final_signal','agent_explanations']:
    try:
        print(f"{f}:", getattr(res, f))
    except Exception as e:
        print(f"{f} access failed: {e}")

