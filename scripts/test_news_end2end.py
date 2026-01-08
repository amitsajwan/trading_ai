import sys
from pprint import pprint

# Ensure local src is importable
sys.path.insert(0, "news_module/src")

from fastapi.testclient import TestClient
from news_module.api_service import app

client = TestClient(app)

print("Calling GET /health")
resp = client.get('/health')
print(resp.status_code)
pprint(resp.json())

print('\nCalling GET /api/v1/news/BANKNIFTY')
resp = client.get('/api/v1/news/BANKNIFTY')
print(resp.status_code)
try:
    pprint(resp.json())
except Exception as e:
    print('Failed to parse JSON:', e)

print('\nCalling GET /api/v1/news/BANKNIFTY/sentiment')
resp = client.get('/api/v1/news/BANKNIFTY/sentiment')
print(resp.status_code)
try:
    pprint(resp.json())
except Exception as e:
    print('Failed to parse JSON:', e)

print('\nCalling POST /api/v1/news/collect')
resp = client.post('/api/v1/news/collect', json={})
print(resp.status_code)
try:
    pprint(resp.json())
except Exception as e:
    print('Failed to parse JSON:', e)
