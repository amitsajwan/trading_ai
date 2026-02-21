from datetime import datetime, timedelta, timezone

from market_data.volume_utils import compute_volume_diff, extract_volume_fields


def test_extract_volume_prefers_candle_volume():
    tick = {
        "candle_volume": 12,
        "volume_traded": 1050,
        "cumulative_volume": 1040,
        "volume": 9,
    }

    value, kind = extract_volume_fields(tick)
    assert value == 12
    assert kind == "delta"


def test_extract_volume_uses_zerodha_cumulative_field():
    tick = {
        "volume_traded": "2100",
        "volume": 10,
    }

    value, kind = extract_volume_fields(tick)
    assert value == 2100
    assert kind == "cumulative"


def test_extract_volume_falls_back_to_volume():
    tick = {"volume": 50}

    value, kind = extract_volume_fields(tick)
    assert value == 50
    assert kind == "delta"


def test_compute_volume_diff_first_tick_seeds_baseline():
    last_volume = {}
    last_timestamp = {}
    now = datetime(2026, 2, 17, 9, 15, tzinfo=timezone.utc)

    diff = compute_volume_diff(
        "BANKNIFTY26MARFUT",
        1000,
        now,
        last_volume=last_volume,
        last_timestamp=last_timestamp,
    )

    assert diff == 0
    assert last_volume["BANKNIFTY26MARFUT"] == 1000
    assert last_timestamp["BANKNIFTY26MARFUT"] == now


def test_compute_volume_diff_returns_incremental_delta():
    now = datetime(2026, 2, 17, 9, 15, tzinfo=timezone.utc)
    last_volume = {"BANKNIFTY26MARFUT": 1000}
    last_timestamp = {"BANKNIFTY26MARFUT": now}

    diff = compute_volume_diff(
        "BANKNIFTY26MARFUT",
        1030,
        now + timedelta(seconds=5),
        last_volume=last_volume,
        last_timestamp=last_timestamp,
    )

    assert diff == 30


def test_compute_volume_diff_resets_after_gap():
    now = datetime(2026, 2, 17, 9, 15, tzinfo=timezone.utc)
    last_volume = {"BANKNIFTY26MARFUT": 1000}
    last_timestamp = {"BANKNIFTY26MARFUT": now}

    diff = compute_volume_diff(
        "BANKNIFTY26MARFUT",
        1400,
        now + timedelta(minutes=6),
        last_volume=last_volume,
        last_timestamp=last_timestamp,
        reset_gap_seconds=300,
    )

    assert diff == 0
    assert last_volume["BANKNIFTY26MARFUT"] == 1400


def test_compute_volume_diff_handles_cumulative_reset():
    now = datetime(2026, 2, 17, 9, 15, tzinfo=timezone.utc)
    last_volume = {"BANKNIFTY26MARFUT": 5000}
    last_timestamp = {"BANKNIFTY26MARFUT": now}

    diff = compute_volume_diff(
        "BANKNIFTY26MARFUT",
        40,
        now + timedelta(seconds=5),
        last_volume=last_volume,
        last_timestamp=last_timestamp,
    )

    assert diff == 0
    assert last_volume["BANKNIFTY26MARFUT"] == 40
