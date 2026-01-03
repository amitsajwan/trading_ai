from monitoring.llm_monitor import LLMMonitor
import types


class DummyManager:
    def get_provider_status(self):
        return {
            'openai': {'status': 'available', 'tokens_today': 100, 'daily_token_quota': 1000},
            'groq': {'status': 'rate_limited', 'tokens_today': 950, 'daily_token_quota': 1000}
        }


class FakeCollection:
    def __init__(self):
        self.inserted = []
    def insert_one(self, doc):
        self.inserted.append(doc)


class FakeDB(dict):
    pass


def test_llm_monitor_writes_alerts(monkeypatch):
    monitor = LLMMonitor()
    # Replace manager
    monitor.manager = DummyManager()

    # Fake mongo client
    fake_alerts = FakeCollection()
    fake_db = {'alerts': fake_alerts}
    class FakeClient:
        def __getitem__(self, name):
            return fake_db
    import monitoring.llm_monitor as lm
    monkeypatch.setattr(lm, 'get_mongo_client', lambda: FakeClient())
    monkeypatch.setattr(lm, 'get_collection', lambda db, name: fake_alerts)

    status = monitor.check()
    assert 'groq' in status
    # Should have written at least one alert for groq rate_limited or near quota
    assert len(fake_alerts.inserted) >= 1