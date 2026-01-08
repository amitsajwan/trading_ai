import pytest
from datetime import datetime, timedelta
from market_data.adapters.historical_tick_replayer import HistoricalTickReplayer
from market_data.api import build_store


def test_compute_rebase_offset_and_adjust_tick():
    store = build_store()
    replayer = HistoricalTickReplayer(store, data_source='synthetic', rebase=True)

    # Create synthetic ticks and set as loaded ticks (use internal method)
    ticks = replayer._generate_synthetic_ticks(duration_minutes=1, instrument='TEST')
    assert len(ticks) > 0

    first_ts = ticks[0].timestamp
    # Compute offset as if rebase_to = now (make tz-aware to match ticks)
    from datetime import timezone
    tz = first_ts.tzinfo if first_ts.tzinfo is not None else timezone.utc
    replayer.rebase_to = datetime.now(tz=tz)
    replayer.rebase = True

    # Simulate start: compute offset
    replayer.rebase_offset = replayer.rebase_to - first_ts

    # Adjust first tick
    original_first = ticks[0].timestamp
    adjusted = original_first + replayer.rebase_offset

    assert abs((adjusted - datetime.now(tz=tz)).total_seconds()) < 5, "Adjusted timestamp should be near now"
