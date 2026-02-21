"""Shared helpers for extracting and differencing live volume fields."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, MutableMapping, Optional, Tuple


def extract_volume_fields(tick_data: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """Return normalized volume value and kind.

    Kinds:
    - "delta": per-tick/per-candle volume
    - "cumulative": cumulative traded volume
    - "missing": no valid volume field found
    """
    if "candle_volume" in tick_data and tick_data["candle_volume"] is not None:
        try:
            return int(tick_data["candle_volume"]), "delta"
        except (TypeError, ValueError):
            pass

    for key in ("volume_traded", "cumulative_volume"):
        if key in tick_data and tick_data[key] is not None:
            try:
                return int(tick_data[key]), "cumulative"
            except (TypeError, ValueError):
                pass

    if "volume" in tick_data and tick_data["volume"] is not None:
        try:
            return int(tick_data["volume"]), "delta"
        except (TypeError, ValueError):
            pass

    return None, "missing"


def compute_volume_diff(
    instrument_name: str,
    current_volume: int,
    timestamp: datetime,
    *,
    last_volume: MutableMapping[str, int],
    last_timestamp: MutableMapping[str, datetime],
    reset_gap_seconds: int = 300,
) -> int:
    """Compute delta volume from cumulative volume with startup/reset guards."""
    if instrument_name not in last_volume:
        last_volume[instrument_name] = current_volume
        last_timestamp[instrument_name] = timestamp
        return 0

    previous_volume = int(last_volume.get(instrument_name, 0) or 0)
    previous_timestamp = last_timestamp.get(instrument_name)

    gap_reset = (
        previous_timestamp is not None
        and (timestamp - previous_timestamp).total_seconds() > reset_gap_seconds
    )
    rollover_reset = current_volume < previous_volume

    if gap_reset or rollover_reset:
        diff = 0
    else:
        diff = max(0, current_volume - previous_volume)

    last_volume[instrument_name] = current_volume
    last_timestamp[instrument_name] = timestamp
    return diff
