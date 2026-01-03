import pytest
from dashboard_pro import add_camel_aliases


def test_add_camel_aliases_simple():
    sample = {
        "entry_price": 150.0,
        "exit_price": 160.0,
        "entry_timestamp": "2026-01-03T00:00:00"
    }

    out = add_camel_aliases(sample)
    assert out["entry_price"] == 150.0
    assert out["entryprice"] == 150.0
    assert out["entryPrice"] == 150.0
    assert out["exitprice"] == 160.0
    assert out["exitPrice"] == 160.0
    assert out["entrytimestamp"] == "2026-01-03T00:00:00"
    assert out["entryTimestamp"] == "2026-01-03T00:00:00"


def test_add_camel_aliases_nested():
    sample = {
        "agents": [
            {"agent_name": "macro", "score_value": 0.7},
            {"agent_name": "micro", "score_value": 0.2}
        ]
    }

    out = add_camel_aliases(sample)
    assert isinstance(out["agents"], list)
    assert out["agents"][0]["score_value"] == 0.7
    assert out["agents"][0]["scorevalue"] == 0.7
    assert out["agents"][0]["scoreValue"] == 0.7
