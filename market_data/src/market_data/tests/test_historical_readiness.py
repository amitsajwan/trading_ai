import asyncio
import pytest

from market_data.runner import start_process


class FakeRedis:
    def __init__(self):
        self._data = {}
        self._keys = []

    def set(self, key, value):
        self._data[key] = value

    def get(self, key):
        return self._data.get(key)

    def delete(self, *keys):
        for k in keys:
            self._data.pop(k, None)

    def keys(self, pattern):
        # simplistic implementation for 'tick:*:latest'
        if pattern == 'tick:*:latest':
            return [k for k in self._data.keys() if k.startswith('tick:') and k.endswith(':latest')]
        return []


@pytest.mark.asyncio
async def test_monitor_for_ticks_sets_data_ready(monkeypatch):
    # Import the coroutine from runner_historical module
    from market_data.runner_historical import monitor_for_ticks

    fake = FakeRedis()

    # Start the monitor in background
    monitor = asyncio.create_task(monitor_for_ticks(fake, timeout=2, interval=0.1))

    # After a short delay, write a tick key
    await asyncio.sleep(0.2)
    fake.set('tick:BANKNIFTY:latest', '{"last_price": 100}')

    res = await monitor
    assert res is True
    # After monitor sets, it should have set data_ready
    assert fake.get('system:historical:data_ready') == '1'
