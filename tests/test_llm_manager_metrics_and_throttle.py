import os
import time
from agents.llm_provider_manager import get_llm_manager
from types import SimpleNamespace


def test_metrics_contains_usage_and_strategy():
    m = get_llm_manager()
    # Ensure strategy field is present
    assert hasattr(m, 'selection_strategy')
    # usage counter dict exists
    assert isinstance(getattr(m, 'provider_usage_counter', {}), dict)


def test_soft_throttle_behavior(monkeypatch):
    # Set low throttle threshold
    monkeypatch.setenv('LLM_SOFT_THROTTLE', '2')
    # Create fresh manager instance
    # Force recreation by clearing global
    import importlib
    import agents.llm_provider_manager as manager_mod
    importlib.reload(manager_mod)
    m = manager_mod.get_llm_manager()

    # Ensure we have at least 2 providers available
    providers = [n for n, cfg in m.providers.items() if cfg.status == manager_mod.ProviderStatus.AVAILABLE and n != 'ollama']
    assert len(providers) >= 2

    # Rapidly select the same provider more than threshold times and verify throttling occurs
    target = providers[0]
    # Simulate rapid selections recorded
    for i in range(3):
        m._record_usage(target)

    # Now _is_throttled should be True for target
    assert m._is_throttled(target)

    # But overall get_provider_for_agent should still return a provider (other than target) when parallel
    p = m.get_provider_for_agent('test_agent', parallel_group='analysis_parallel')
    assert p is not None
    assert p != target or len(providers) == 1
