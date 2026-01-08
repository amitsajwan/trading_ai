import requests

try:
    response = requests.get('http://localhost:8000/api/options-chain', timeout=5)
    print('Status:', response.status_code)
    if response.status_code == 200:
        data = response.json()
        print('Available:', data.get('available'))
        print('Futures price:', data.get('futures_price'))
        print('Chain length:', len(data.get('chain', [])))
    else:
        print('Response:', response.text)
except Exception as e:
    print('Error:', e)





