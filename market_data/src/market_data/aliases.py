"""Canonical instrument aliases for NIFTY, BANKNIFTY, and futures."""
from typing import Tuple
import re

canonical_instruments: Tuple[str, str] = ("BANKNIFTY", "NIFTY")

_alias_map = {
    "BANKNIFTY": "BANKNIFTY",
    "BANK NIFTY": "BANKNIFTY",
    "NIFTY BANK": "BANKNIFTY",
    "NIFTYBANK": "BANKNIFTY",
    "CNXBANK": "BANKNIFTY",
    "NSE:BANKNIFTY": "BANKNIFTY",
    "NIFTY": "NIFTY",
    "NIFTY 50": "NIFTY",
    "NIFTY50": "NIFTY",
    "NSE:NIFTY": "NIFTY",
    "NSEI": "NIFTY",
}


def _sanitize(text: str) -> str:
    return " ".join(text.upper().replace("_", " ").replace("-", " ").split())


def normalize_instrument(symbol: str) -> str:
    """Return a canonical symbol or raise for unsupported values."""
    cleaned = _sanitize(symbol or "")
    if cleaned in _alias_map:
        return _alias_map[cleaned]

    compact = cleaned.replace(" ", "")
    if compact in _alias_map:
        return _alias_map[compact]

    # Handle futures symbols (e.g., BANKNIFTY26JANFUT, NIFTY26JANFUT)
    if re.match(r'^(BANKNIFTY|NIFTY)\d{2}[A-Z]{3}FUT$', cleaned):
        return cleaned

    raise ValueError(f"Unsupported instrument: {symbol}")

