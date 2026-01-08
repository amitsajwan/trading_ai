from ui_shell.contracts import UIDataProvider, UIDispatcher


def test_ui_protocols_present():
    assert hasattr(UIDataProvider, "get_snapshot")
    assert hasattr(UIDataProvider, "get_metrics")
    assert hasattr(UIDispatcher, "publish")

