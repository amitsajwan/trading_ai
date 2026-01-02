"""Check Zerodha credentials."""
import sys
import os
import json
from pathlib import Path
sys.path.insert(0, os.getcwd())

try:
    cred_path = Path('credentials.json')
    if not cred_path.exists():
        print('ZERODHA_NO_CREDENTIALS')
        sys.exit(1)
    
    with open(cred_path) as f:
        creds = json.load(f)
    
    if not creds.get('access_token'):
        print('ZERODHA_NO_TOKEN')
        sys.exit(1)
    
    # Try to connect
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=creds.get('api_key', ''))
    kite.set_access_token(creds.get('access_token', ''))
    
    # Test connection
    profile = kite.profile()
    print('ZERODHA_OK', profile.get('user_name', 'Unknown'))
    sys.exit(0)
except ImportError:
    print('ZERODHA_MODULE_MISSING')
    sys.exit(1)
except Exception as e:
    print('ZERODHA_ERROR', str(e)[:50])
    sys.exit(1)

