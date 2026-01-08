"""Verify .env file configuration."""

from pathlib import Path
import re

def verify_env():
    """Verify .env file has all required configurations."""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("ERROR: .env file not found!")
        return False
    
    content = env_file.read_text()
    
    # Required instrument configs
    required_configs = {
        "INSTRUMENT_SYMBOL": None,
        "INSTRUMENT_NAME": None,
        "INSTRUMENT_EXCHANGE": None,
        "DATA_SOURCE": None,
        "NEWS_QUERY": None,
        "NEWS_KEYWORDS": None,
        "MACRO_DATA_ENABLED": None,
        "MARKET_24_7": None,
        "MARKET_OPEN_TIME": None,
        "MARKET_CLOSE_TIME": None,
    }
    
    print("=" * 70)
    print("Verifying .env Configuration")
    print("=" * 70)
    
    all_found = True
    for key in required_configs.keys():
        # Search for KEY=value pattern
        match = re.search(rf'^{key}=(.*)$', content, re.MULTILINE)
        if match:
            value = match.group(1).strip()
            required_configs[key] = value
            print(f"[OK] {key:25} = {value}")
        else:
            print(f"[MISSING] {key:25} = NOT FOUND")
            all_found = False
    
    print("=" * 70)
    
    if all_found:
        print("SUCCESS: All instrument configurations found!")
        
        # Show current instrument
        instrument = required_configs.get("INSTRUMENT_NAME", "Unknown")
        data_source = required_configs.get("DATA_SOURCE", "Unknown")
        print(f"\nCurrent Instrument: {instrument}")
        print(f"Data Source: {data_source}")
        print(f"24/7 Market: {required_configs.get('MARKET_24_7', 'Unknown')}")
    else:
        print("ERROR: Some configurations are missing!")
        print("\nRun: python scripts/configure_instrument.py <BTC|BANKNIFTY|NIFTY>")
    
    return all_found

if __name__ == "__main__":
    verify_env()


