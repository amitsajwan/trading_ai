import warnings
from fastapi.testclient import TestClient

from news_module.api_service import app


def test_collect_and_get_news_no_unclosed_sessions():
    """Integration test: POST /api/v1/news/collect then GET /api/v1/news/BANKNIFTY.

    Asserts that news are collected/stored and no aiohttp unclosed sessions or connectors
    are emitted as warnings.
    """
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        client = TestClient(app)

        # Trigger collection (no body)
        resp = client.post('/api/v1/news/collect')
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('status') == 'success'
        assert isinstance(data.get('collected_count'), int)

        # Fetch news for an instrument
        resp2 = client.get('/api/v1/news/BANKNIFTY')
        assert resp2.status_code == 200
        news_list = resp2.json().get('news', [])

        # If we have any news, check required fields
        if news_list:
            item = news_list[0]
            assert 'title' in item
            assert 'source' in item
            assert 'published_at' in item
            assert 'sentiment_score' in item
            assert 'sentiment_label' in item

        # Check sentiment endpoint
        resp3 = client.get('/api/v1/news/BANKNIFTY/sentiment')
        assert resp3.status_code == 200
        sentiment = resp3.json()
        assert 'average_sentiment' in sentiment

        # Ensure no unclosed client session warnings
        messages = [str(x.message) for x in w]
        assert not any('Unclosed client session' in m or 'Unclosed connector' in m for m in messages), (
            f"Found resource warnings: {messages}"
        )
