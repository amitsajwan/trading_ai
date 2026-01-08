import requests
import json

try:
    response = requests.post('http://localhost:8006/api/v1/analyze', json={'instrument': 'BANKNIFTY', 'context': {}})
    print(f'Status: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(f'Decision: {data.get("decision", "N/A")}')
        print(f'Confidence: {data.get("confidence", "N/A")}')
        print('✅ Analyze endpoint working!')
    else:
        print(f'Error: {response.text}')
except Exception as e:
    print(f'Error: {e}')