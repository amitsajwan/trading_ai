"""Check Binance connectivity and return BINANCE_OK <price> on success."""
import sys
import json
import urllib.request

symbol = 'BTCUSDT'
if len(sys.argv) > 1:
    # allow passing an explicit symbol or instrument
    inst = sys.argv[1].upper()
    if inst == 'BTC':
        symbol = 'BTCUSDT'
    else:
        # accept raw symbol like BTCUSDT
        symbol = sys.argv[1]

url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}'

try:
    with urllib.request.urlopen(url, timeout=5) as response:
        data = json.loads(response.read().decode())
        price = data.get('price')
        if price:
            print('BINANCE_OK', price)
            sys.exit(0)
        else:
            print('BINANCE_ERROR', 'No price in response')
            sys.exit(1)
except urllib.error.URLError as e:
    print('BINANCE_ERROR', str(e)[:200])
    sys.exit(1)
except Exception as e:
    print('BINANCE_ERROR', str(e)[:200])
    sys.exit(1)

