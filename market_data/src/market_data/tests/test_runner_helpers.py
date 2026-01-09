import time

from market_data.runner import wait_for_historical_ready


class FakeRedis:
    def __init__(self):
        self._data = {}

    def set(self, key, value):
        self._data[key] = value

    def get(self, key):
        return self._data.get(key)


def test_wait_for_historical_ready_success():
    fake = FakeRedis()

    # Set key after a short delay in background
    def setter():
        time.sleep(0.2)
        fake.set('system:historical:data_ready', '1')

    import threading
    t = threading.Thread(target=setter)
    t.start()

    ok = wait_for_historical_ready(fake, timeout=2, poll_interval=0.05)
    assert ok is True
    t.join()


def test_wait_for_historical_ready_timeout():
    fake = FakeRedis()
    ok = wait_for_historical_ready(fake, timeout=0.2, poll_interval=0.05)
    assert ok is False
