#!/usr/bin/env python3
import requests

try:
    response = requests.get('http://localhost:8004/api/v1/options/chain/BANKNIFTY', timeout=10)
    if response.status_code == 200:
        data = response.json()
        print(f'Underlying price: {data.get("underlying_price")}')
        puts = data.get('puts', [])
        calls = data.get('calls', [])
        print(f'Available puts: {len(puts)}')
        print(f'Available calls: {len(calls)}')

        # Show some put strikes
        print('Sample puts:')
        for p in puts[:5]:
            print(f'  Strike: {p.get("strike")}, OI: {p.get("oi")}, Volume: {p.get("volume")}')

        print('Sample calls:')
        for c in calls[:5]:
            print(f'  Strike: {c.get("strike")}, OI: {c.get("oi")}, Volume: {c.get("volume")}')
    else:
        print(f'Error: {response.status_code} - {response.text}')
except Exception as e:
    print(f'Error: {e}')