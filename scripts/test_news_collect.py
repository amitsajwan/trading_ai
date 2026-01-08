import sys
sys.path.insert(0, 'news_module/src')
from fastapi.testclient import TestClient
from news_module.api_service import app

c = TestClient(app)
r = c.post('/api/v1/news/collect')
print('status', r.status_code)
from pprint import pprint
pprint(r.json())
