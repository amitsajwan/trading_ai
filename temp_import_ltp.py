import sys, os
sys.path.insert(0, r"C:\code\zerodha\market_data\src")
from market_data.collectors import ltp_collector as l
print('ltp module file:', getattr(l, '__file__', None))
import inspect
print('classes in module:', [name for name, obj in inspect.getmembers(l, inspect.isclass) if obj.__module__ == l.__name__])
print('module dir sample:', dir(l)[:200])
print('module attrs (contains "LTP"):', [a for a in dir(l) if 'LTP' in a])
print('has LTPDataCollector:', hasattr(l, 'LTPDataCollector'))
print('has build_kite_client:', hasattr(l, 'build_kite_client'))
