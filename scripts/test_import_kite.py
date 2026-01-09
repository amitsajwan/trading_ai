import sys, importlib, traceback
sys.path.insert(0, '.')
sys.path.insert(0, './market_data/src')
print('sys.path prepared')
try:
    m = importlib.import_module('market_data.tools.kite_auth_service')
    print('imported market_data.tools.kite_auth_service', m)
    from kite_auth_service import KiteAuthService
    print('imported KiteAuthService shim OK')
except Exception as e:
    traceback.print_exc()