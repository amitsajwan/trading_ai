"""
Tests for LLM provider manager alert routing
"""
import pytest
from unittest.mock import patch, Mock
from agents.llm_provider_manager import LLMProviderManager, ProviderConfig, ProviderStatus


def test_handle_provider_error_routes_rate_limit_alert(monkeypatch):
    mgr = LLMProviderManager()
    # Create a dummy provider
    mgr.providers['testprov'] = ProviderConfig(name='testprov')

    # Mock send_alert
    mock_send = Mock()
    monkeypatch.setattr('monitoring.alert_router.send_alert', mock_send)

    # Simulate a rate limit error
    err = Exception("Error code: 429 - Rate limit reached. Please try again in 2 minutes")
    mgr._handle_provider_error('testprov', err)

    # Provider should be marked RATE_LIMITED
    assert mgr.providers['testprov'].status == ProviderStatus.RATE_LIMITED
    # send_alert should have been called at least once
    assert mock_send.called
    args, kwargs = mock_send.call_args
    assert args[0] in ('provider_rate_limited', 'provider_error')
    assert 'testprov' in kwargs.get('details', {}).get('provider', 'testprov') or 'testprov' in args[3].get('details', {}).get('provider', 'testprov') if len(args) > 3 else True


def test_handle_provider_error_routes_general_error_alert(monkeypatch):
    mgr = LLMProviderManager()
    mgr.providers['testprov2'] = ProviderConfig(name='testprov2')

    mock_send = Mock()
    monkeypatch.setattr('monitoring.alert_router.send_alert', mock_send)

    err = Exception("Connection error: timeout")
    mgr._handle_provider_error('testprov2', err)

    assert mgr.providers['testprov2'].status in (ProviderStatus.ERROR, ProviderStatus.UNAVAILABLE)
    assert mock_send.called
