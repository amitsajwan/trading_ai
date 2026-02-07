import sys, os
sys.path.insert(0, r"C:\code\zerodha\market_data\src")
import importlib
mod_name = 'market_data.collectors.ltp_collector'
if mod_name in sys.modules:
    del sys.modules[mod_name]
try:
    m = importlib.import_module(mod_name)
    print('imported', m, 'file=', getattr(m,'__file__', None))
    print('attrs present:', [a for a in dir(m) if 'LTP' in a])
    print('has LTPDataCollector:', hasattr(m, 'LTPDataCollector'))
    print('has build_kite_client:', hasattr(m, 'build_kite_client'))
except Exception as e:
    print('import failed', e)
    import traceback; traceback.print_exc()
