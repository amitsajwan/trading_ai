import webbrowser

from data_niftybank.tools.login_test import *


def test_login_test_opens_browser(monkeypatch):
    class MockKite:
        def __init__(self, api_key):
            pass
        def login_url(self):
            return "http://login"

    monkeypatch.setattr(login_test, "KiteConnect", MockKite)

    called = {}
    def fake_open(url):
        called['url'] = url
    monkeypatch.setattr(webbrowser, "open", fake_open)

    login_test.main()
    assert called['url'] == "http://login"
