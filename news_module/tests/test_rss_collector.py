import asyncio
import pytest
from types import SimpleNamespace

from news_module.collectors.rss_collector import RSSNewsCollector
from news_module.contracts import NewsSource


class DummyResponse:
    def __init__(self, status: int, text: str):
        self.status = status
        self._text = text

    async def text(self):
        return self._text


class DummyContext:
    def __init__(self, resp):
        self.resp = resp

    async def __aenter__(self):
        return self.resp

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummySession403:
    def get(self, url):
        return DummyContext(DummyResponse(403, ""))


class DummySessionError:
    def get(self, url):
        class ErrorContext:
            async def __aenter__(self):
                raise RuntimeError("timeout")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        return ErrorContext()


@pytest.mark.asyncio
async def test_collect_handles_403():
    source = NewsSource(name="test", url="http://example.test/rss", type="rss")
    collector = RSSNewsCollector([source])
    collector.session = DummySession403()

    items = await collector.collect_news()
    assert isinstance(items, list)
    assert items == []


@pytest.mark.asyncio
async def test_collect_handles_exception():
    source = NewsSource(name="test", url="http://example.test/rss", type="rss")
    collector = RSSNewsCollector([source])
    collector.session = DummySessionError()

    items = await collector.collect_news()
    assert isinstance(items, list)
    assert items == []
