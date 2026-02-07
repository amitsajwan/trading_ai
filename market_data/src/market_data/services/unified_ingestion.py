"""Unified market-data ingestion service.

Runs in one process and manages collectors or replay based on TRADING_MODE.
Modes:
- live: start websocket + LTP + depth collectors
- historical: start historical replay per instrument
- mock: start synthetic replay per instrument
"""
from __future__ import annotations

import os
import sys
import time
from typing import Dict, List, Optional

from market_data.runtime import start_process

PYTHON = sys.executable


def _parse_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_instruments() -> List[Dict[str, str]]:
    symbols = _parse_list(os.getenv("INSTRUMENTS"))
    if not symbols:
        default_symbol = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26FEBFUT")
        symbols = [default_symbol]

    trading_symbols = _parse_list(os.getenv("INSTRUMENT_TRADING_SYMBOLS"))
    if not trading_symbols:
        default_trading_symbol = os.getenv("INSTRUMENT_TRADING_SYMBOL", "")
        trading_symbols = [default_trading_symbol] if default_trading_symbol else []

    exchanges = _parse_list(os.getenv("INSTRUMENT_EXCHANGES"))
    if not exchanges:
        default_exchange = os.getenv("INSTRUMENT_EXCHANGE", "NFO")
        exchanges = [default_exchange]

    configs: List[Dict[str, str]] = []
    for idx, symbol in enumerate(symbols):
        trading_symbol = trading_symbols[idx] if idx < len(trading_symbols) else (trading_symbols[0] if len(trading_symbols) == 1 else "")
        exchange = exchanges[idx] if idx < len(exchanges) else (exchanges[0] if len(exchanges) == 1 else "NFO")
        configs.append({
            "symbol": symbol,
            "trading_symbol": trading_symbol,
            "exchange": exchange,
        })
    return configs


def _build_instrument_env(base_env: Dict[str, str], config: Dict[str, str], mode: str) -> Dict[str, str]:
    env = base_env.copy()
    env["INSTRUMENT_SYMBOL"] = config["symbol"]
    if config.get("trading_symbol"):
        env["INSTRUMENT_TRADING_SYMBOL"] = config["trading_symbol"]
    else:
        env.pop("INSTRUMENT_TRADING_SYMBOL", None)
    env["INSTRUMENT_EXCHANGE"] = config.get("exchange", env.get("INSTRUMENT_EXCHANGE", "NFO"))
    env["EXECUTION_MODE"] = "historical" if mode in ("historical", "mock") else "live"
    return env


def _start_live_collectors(instruments: List[Dict[str, str]]) -> List[tuple[str, object]]:
    procs: List[tuple[str, object]] = []
    base_env = os.environ.copy()

    enable_ws = os.getenv("ENABLE_WEBSOCKET_COLLECTOR", "1").lower() in ("1", "true", "yes")
    enable_ltp = os.getenv("ENABLE_LTP_PROCESSOR", "1").lower() in ("1", "true", "yes")
    enable_depth = os.getenv("ENABLE_DEPTH_COLLECTOR", "1").lower() in ("1", "true", "yes")

    for instrument in instruments:
        env = _build_instrument_env(base_env, instrument, "live")

        label = instrument.get("symbol")
        if enable_ws:
            cmd = [PYTHON, "-m", "market_data.sources.websocket"]
            procs.append((f"WebSocket Collector ({label})", start_process(f"WebSocket Collector ({label})", cmd, env=env)))
        if enable_ltp:
            cmd = [PYTHON, "-m", "market_data.processors.volume_enhancer"]
            procs.append((f"LTP Processor ({label})", start_process(f"LTP Processor ({label})", cmd, env=env)))
        if enable_depth:
            cmd = [PYTHON, "-m", "market_data.sources.depth"]
            procs.append((f"Depth Collector ({label})", start_process(f"Depth Collector ({label})", cmd, env=env)))

    return procs


def _start_replay(instruments: List[Dict[str, str]], mode: str) -> List[tuple[str, object]]:
    procs: List[tuple[str, object]] = []
    base_env = os.environ.copy()

    if mode == "mock" and not os.getenv("HISTORICAL_SOURCE"):
        base_env["HISTORICAL_SOURCE"] = "synthetic"

    for instrument in instruments:
        env = _build_instrument_env(base_env, instrument, mode)
        cmd = [PYTHON, "-m", "market_data.runner_historical"]
        label = instrument.get("symbol")
        name = f"{mode.capitalize()} Replay ({label})"
        procs.append((name, start_process(name, cmd, env=env)))

    return procs


def main() -> None:
    mode = os.getenv("TRADING_MODE", "live").lower()
    instruments = _resolve_instruments()

    procs: List[tuple[str, object]] = []
    try:
        if mode == "live":
            procs = _start_live_collectors(instruments)
        elif mode in ("historical", "mock"):
            procs = _start_replay(instruments, mode)
        else:
            raise SystemExit(f"Unsupported TRADING_MODE: {mode}")

        print(f"[market_data] Unified ingestion running in {mode} mode with {len(instruments)} instrument(s)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[market_data] Stopping unified ingestion...")
        for name, proc in procs:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                print(f"[market_data] Stopped {name}")
            except Exception:
                try:
                    proc.kill()
                    print(f"[market_data] Killed {name}")
                except Exception:
                    pass


if __name__ == "__main__":
    main()
