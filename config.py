"""Configuration module for market data system."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


def _load_env_candidates() -> None:
    """Load environment from known .env files without overriding existing vars."""
    if load_dotenv is None:
        return

    cwd = Path.cwd()
    here = Path(__file__).resolve().parent
    candidates = [
        cwd / ".env",
        here / ".env",
        here / "market_data" / ".env",
        here / "market_data_dashboard" / ".env",
    ]
    seen = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            try:
                load_dotenv(dotenv_path=path, override=False)
            except Exception:
                pass


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _first_non_empty(*values: Optional[str]) -> str:
    for value in values:
        if value is None:
            continue
        item = str(value).strip()
        if item:
            return item
    return ""


def _default_instrument_symbol() -> str:
    return _first_non_empty(
        os.getenv("INSTRUMENT_SYMBOL"),
        os.getenv("INSTRUMENT_KEY"),
        os.getenv("INSTRUMENT_TRADING_SYMBOL"),
        os.getenv("DEFAULT_INSTRUMENT_SYMBOL"),
        "INSTRUMENT_NOT_SET",
    )


_load_env_candidates()


@dataclass
class Config:
    """System configuration."""

    instrument_symbol: str = ""
    instrument_key: str = ""
    instrument_trading_symbol: str = ""
    instrument_exchange: str = "NFO"
    exchange: str = "NFO"
    mode: str = "live"  # live, historical, paper

    def get_redis_config(self, decode_responses: bool = True, db: Optional[int] = None):
        """Get Redis configuration from environment."""
        redis_db = _env_int("REDIS_DB", 0) if db is None else int(db)
        return {
            "host": _first_non_empty(os.getenv("REDIS_HOST"), "localhost"),
            "port": _env_int("REDIS_PORT", 6379),
            "db": redis_db,
            "decode_responses": bool(decode_responses),
        }

    def get_mongo_config(self):
        """Get Mongo configuration from environment."""
        mongo_uri = _first_non_empty(os.getenv("MONGODB_URI"), os.getenv("MONGO_URI"))
        if mongo_uri:
            return {"uri": mongo_uri}
        return {
            "host": _first_non_empty(os.getenv("MONGO_HOST"), "localhost"),
            "port": _env_int("MONGO_PORT", 27017),
            "db": _first_non_empty(os.getenv("MONGO_DB"), "trading_ai"),
        }

    def get_kite_config(self):
        """Get Kite auth configuration from environment."""
        return {
            "api_key": _first_non_empty(os.getenv("KITE_API_KEY")),
            "api_secret": _first_non_empty(os.getenv("KITE_API_SECRET")),
            "access_token": _first_non_empty(os.getenv("KITE_ACCESS_TOKEN")),
            "credentials_path": _first_non_empty(os.getenv("KITE_CREDENTIALS_PATH"), "credentials.json"),
        }

    @property
    def redis_price_key(self):
        """Get Redis price key for this instrument."""
        return f"price:{self.instrument_key}"


def get_config() -> Config:
    """Get system configuration from environment variables."""
    instrument_symbol = _default_instrument_symbol()
    instrument_key = _first_non_empty(os.getenv("INSTRUMENT_KEY"), instrument_symbol)
    instrument_trading_symbol = _first_non_empty(os.getenv("INSTRUMENT_TRADING_SYMBOL"), instrument_symbol)
    instrument_exchange = _first_non_empty(os.getenv("INSTRUMENT_EXCHANGE"), "NFO")
    exchange = _first_non_empty(os.getenv("EXCHANGE"), instrument_exchange)
    mode = _first_non_empty(os.getenv("MODE"), "live")

    return Config(
        instrument_symbol=instrument_symbol,
        instrument_key=instrument_key,
        instrument_trading_symbol=instrument_trading_symbol,
        instrument_exchange=instrument_exchange,
        exchange=exchange,
        mode=mode,
    )


if __name__ == "__main__":
    config = get_config()
    print("Configuration loaded:")
    print(f"  Instrument: {config.instrument_symbol}")
    print(f"  Key: {config.instrument_key}")
    print(f"  Exchange: {config.exchange}")
    print(f"  Mode: {config.mode}")
