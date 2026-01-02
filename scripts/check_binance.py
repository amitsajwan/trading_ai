"""Check Binance API connectivity."""
import sys
import os
import urllib.request
import json
sys.path.insert(0, os.getcwd())

try:
    from config.settings import settings
    
    # Use Binance REST API instead of WebSocket for connectivity check
    symbol = 'BTCUSDT'
    url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}'
    
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data.get('price'):
                price = float(data.get('price'))
                print('BINANCE_OK', price)
                sys.exit(0)
            else:
                print('BINANCE_ERROR', 'No price in response')
                sys.exit(1)
    except urllib.error.URLError as e:
        print('BINANCE_ERROR', str(e)[:50])
        sys.exit(1)
    except Exception as e:
        print('BINANCE_ERROR', str(e)[:50])
        sys.exit(1)
except Exception as e:
    print('ERROR', str(e)[:50])
    sys.exit(1)

