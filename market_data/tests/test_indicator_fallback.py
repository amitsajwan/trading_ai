import redis
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

# Ensure PYTHONPATH points to market_data/src when running tests in CI; tests run locally with project PYTHONPATH


def make_bar(ts, base=100.0):
    return {
        'timestamp': ts.isoformat(),
        'open': base,
        'high': base + 1.0,
        'low': base - 1.0,
        'close': base + 0.5,
        'volume': 1000,
        '_format_version': '2.0'
    }


def test_indicator_endpoint_falls_back_to_sorted_set():
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    instr = 'FALLBACK_TEST'
    timeframe = '1min'

    # Clean up any existing keys
    for k in r.keys(f'ohlc:{instr}:{timeframe}:*'):
        r.delete(k)
    sorted_key = f'ohlc_sorted:{instr}:{timeframe}'
    if r.exists(sorted_key):
        r.delete(sorted_key)

    # Populate sorted set with 25 bars
    now = datetime.utcnow()
    for i in range(25):
        ts = now - timedelta(minutes=25 - i)
        bar = make_bar(ts, base=60000.0 + i)
        r.zadd(sorted_key, {json.dumps(bar, default=str): ts.timestamp()})

    # Import the FastAPI app and use TestClient to call the indicators endpoint
    from market_data.api_service import app

    client = TestClient(app)

    resp = client.get(f"/api/v1/technical/indicators/{instr}?timeframe=1min")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get('instrument') == instr
    indicators = data.get('indicators')
    assert indicators is not None
    # Check existence of a basic indicator
    assert 'rsi_14' in indicators and 'macd_value' in indicators
