"""Show what changes when switching instruments."""

from pathlib import Path
import re

def show_env_changes():
    """Show current .env instrument configuration."""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("ERROR: .env file not found!")
        return
    
    content = env_file.read_text()
    
    # Extract instrument-related configs
    instrument_configs = {}
    keys = [
        "INSTRUMENT_SYMBOL", "INSTRUMENT_NAME", "INSTRUMENT_EXCHANGE",
        "DATA_SOURCE", "NEWS_QUERY", "NEWS_KEYWORDS",
        "MACRO_DATA_ENABLED", "MARKET_24_7",
        "MARKET_OPEN_TIME", "MARKET_CLOSE_TIME"
    ]
    
    print("=" * 70)
    print("Current .env Instrument Configuration")
    print("=" * 70)
    
    for key in keys:
        match = re.search(rf'^{key}=(.*)$', content, re.MULTILINE)
        if match:
            value = match.group(1).strip()
            instrument_configs[key] = value
            print(f"{key:25} = {value}")
        else:
            print(f"{key:25} = [NOT SET]")
    
    print("=" * 70)
    
    # Show what will change for each instrument
    print("\nWhat changes when you switch:")
    print("-" * 70)
    
    configs = {
        "BTC": {
            "DATA_SOURCE": "CRYPTO -> Binance WebSocket",
            "MARKET_24_7": "true -> 24/7 trading",
            "MACRO_DATA_ENABLED": "false -> No RBI data",
            "NEWS_QUERY": "Bitcoin/crypto news"
        },
        "BANKNIFTY": {
            "DATA_SOURCE": "ZERODHA -> Zerodha WebSocket",
            "MARKET_24_7": "false -> Market hours only",
            "MACRO_DATA_ENABLED": "true -> RBI data enabled",
            "NEWS_QUERY": "Bank Nifty/banking news"
        },
        "NIFTY": {
            "DATA_SOURCE": "ZERODHA -> Zerodha WebSocket",
            "MARKET_24_7": "false -> Market hours only",
            "MACRO_DATA_ENABLED": "true -> RBI data enabled",
            "NEWS_QUERY": "Nifty 50/Indian market news"
        }
    }
    
    current_instrument = instrument_configs.get("INSTRUMENT_NAME", "Unknown")
    print(f"\nCurrent: {current_instrument}")
    print("\nTo switch, run:")
    print("  python scripts/configure_instrument.py BTC")
    print("  python scripts/configure_instrument.py BANKNIFTY")
    print("  python scripts/configure_instrument.py NIFTY")
    
    print("\n" + "=" * 70)
    print("NOTE: URLs (MongoDB, Redis) do NOT change - they're infrastructure")
    print("Only instrument-specific settings change")
    print("=" * 70)

if __name__ == "__main__":
    show_env_changes()


