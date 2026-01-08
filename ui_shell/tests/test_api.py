"""Test UI Shell API facade functions."""

import pytest

from ui_shell.api import build_ui_data_provider, build_ui_dispatcher, build_ui_shell
from ui_shell.providers import EngineDataProvider
from ui_shell.dispatchers import EngineActionDispatcher


class TestAPIFacade:
    """Test API facade factory functions."""

    def test_build_ui_data_provider(self):
        """Test build_ui_data_provider factory function."""
        provider = build_ui_data_provider()

        assert isinstance(provider, EngineDataProvider)
        # Should use mock engine by default
        assert hasattr(provider, 'engine')

    def test_build_ui_dispatcher(self):
        """Test build_ui_dispatcher factory function."""
        dispatcher = build_ui_dispatcher()

        assert isinstance(dispatcher, EngineActionDispatcher)
        # Should use mock engine by default
        assert hasattr(dispatcher, 'engine')

    def test_build_ui_shell(self):
        """Test build_ui_shell factory function returns tuple."""
        result = build_ui_shell()

        assert isinstance(result, tuple)
        assert len(result) == 2

        provider, dispatcher = result
        assert isinstance(provider, EngineDataProvider)
        assert isinstance(dispatcher, EngineActionDispatcher)

    def test_build_ui_data_provider_with_custom_engine(self):
        """Test build_ui_data_provider with custom engine."""

        class CustomEngine:
            pass

        custom_engine = CustomEngine()
        provider = build_ui_data_provider(custom_engine)

        assert isinstance(provider, EngineDataProvider)
        assert provider.engine is custom_engine

    def test_build_ui_dispatcher_with_custom_engine(self):
        """Test build_ui_dispatcher with custom engine."""

        class CustomEngine:
            pass

        custom_engine = CustomEngine()
        dispatcher = build_ui_dispatcher(custom_engine)

        assert isinstance(dispatcher, EngineActionDispatcher)
        assert dispatcher.engine is custom_engine

    def test_build_ui_shell_with_custom_engine(self):
        """Test build_ui_shell with custom engine."""

        class CustomEngine:
            pass

        custom_engine = CustomEngine()
        provider, dispatcher = build_ui_shell(custom_engine)

        assert provider.engine is custom_engine
        assert dispatcher.engine is custom_engine

