"""Configure instrument via flag (BTC, BANKNIFTY, or NIFTY)."""

import os
import sys
from pathlib import Path

# Instrument configurations
INSTRUMENT_CONFIGS = {
    "BTC": {
        "INSTRUMENT_SYMBOL": "BTC-USD",
        "INSTRUMENT_NAME": "Bitcoin",
        "INSTRUMENT_EXCHANGE": "CRYPTO",
        "DATA_SOURCE": "CRYPTO",
        "NEWS_QUERY": "Bitcoin OR BTC OR cryptocurrency",
        "NEWS_KEYWORDS": "Bitcoin,BTC,cryptocurrency,crypto",
        "MACRO_DATA_ENABLED": "false",
        "MARKET_24_7": "true",
        "MARKET_OPEN_TIME": "00:00:00",
        "MARKET_CLOSE_TIME": "23:59:59",
    },
    "BANKNIFTY": {
        "INSTRUMENT_SYMBOL": "NIFTY BANK",
        "INSTRUMENT_NAME": "Bank Nifty",
        "INSTRUMENT_EXCHANGE": "NSE",
        "DATA_SOURCE": "ZERODHA",
        "NEWS_QUERY": "Bank Nifty OR banking sector OR RBI",
        "NEWS_KEYWORDS": "Bank Nifty,banking sector,RBI",
        "MACRO_DATA_ENABLED": "true",
        "MARKET_24_7": "false",
        "MARKET_OPEN_TIME": "09:15:00",
        "MARKET_CLOSE_TIME": "15:30:00",
    },
    "NIFTY": {
        "INSTRUMENT_SYMBOL": "NIFTY 50",
        "INSTRUMENT_NAME": "Nifty 50",
        "INSTRUMENT_EXCHANGE": "NSE",
        "DATA_SOURCE": "ZERODHA",
        "NEWS_QUERY": "Nifty 50 OR Indian stock market OR Sensex",
        "NEWS_KEYWORDS": "Nifty 50,Indian stock market,Sensex",
        "MACRO_DATA_ENABLED": "true",
        "MARKET_24_7": "false",
        "MARKET_OPEN_TIME": "09:15:00",
        "MARKET_CLOSE_TIME": "15:30:00",
    }
}

def update_env_file(instrument: str):
    """Update .env file with instrument configuration."""
    instrument = instrument.upper()
    
    if instrument not in INSTRUMENT_CONFIGS:
        print(f"ERROR: Invalid instrument: {instrument}")
        print(f"Valid options: {', '.join(INSTRUMENT_CONFIGS.keys())}")
        return False
    
    env_file = Path(".env")
    
    # Read existing .env or create new
    if env_file.exists():
        content = env_file.read_text(encoding='utf-8')
    else:
        content = ""
        print("Creating new .env file...")
    
    lines = content.split('\n')
    updated_lines = []
    config_updated = False
    
    # Get configuration for selected instrument
    config = INSTRUMENT_CONFIGS[instrument]
    
    # Track which configs we've updated
    updated_keys = set()
    
    # Update or add each config
    for line in lines:
        updated = False
        # Check if this line is a config we need to update
        for key, value in config.items():
            if line.strip().startswith(f'{key}='):
                # Update the line
                updated_lines.append(f'{key}={value}')
                updated = True
                updated_keys.add(key)
                config_updated = True
                break
        if not updated:
            # Keep the original line
            updated_lines.append(line)
    
    # Add missing configs at the end (before any existing instrument config section)
    # Find where to insert (before any # comment sections at end)
    insert_idx = len(updated_lines)
    for i in range(len(updated_lines) - 1, -1, -1):
        if updated_lines[i].startswith('#'):
            insert_idx = i + 1
            break
    
    for key, value in config.items():
        if key not in updated_keys:
            updated_lines.insert(insert_idx, f'{key}={value}')
            insert_idx += 1
            config_updated = True
    
    # Add section header if config was updated
    if config_updated:
        # Remove old instrument config headers
        updated_lines = [line for line in updated_lines 
                        if not line.startswith('# ') or 
                        'Configuration' not in line or 
                        'Instrument' not in line]
        
        # Find insertion point (after other configs or at end)
        insert_idx = len(updated_lines)
        for i, line in enumerate(updated_lines):
            if line.startswith('#') and ('LLM' in line or 'Database' in line or 'Trading' in line):
                insert_idx = i
                break
        
        # Insert header and configs
        header = f'# Instrument Configuration ({instrument})'
        updated_lines.insert(insert_idx, '')
        updated_lines.insert(insert_idx, header)
    
    # Write updated .env
    env_file.write_text('\n'.join(updated_lines), encoding='utf-8')
    
    print("=" * 70)
    print(f"Instrument configured: {instrument}")
    print("=" * 70)
    print("\nConfiguration:")
    for key, value in config.items():
        print(f"  {key}={value}")
    print("\n" + "=" * 70)
    
    return True

def main():
    """Main entry point."""
    # Get instrument from command line argument or environment variable
    if len(sys.argv) > 1:
        instrument = sys.argv[1].upper()
    else:
        instrument = os.getenv("TRADING_INSTRUMENT", "").upper()
    
    if not instrument:
        print("Usage: python scripts/configure_instrument.py <INSTRUMENT>")
        print("\nValid instruments:")
        for inst, config in INSTRUMENT_CONFIGS.items():
            print(f"  {inst:12} - {config['INSTRUMENT_NAME']}")
        print("\nOr set environment variable:")
        print("  export TRADING_INSTRUMENT=BTC  # Linux/Mac")
        print("  set TRADING_INSTRUMENT=BTC     # Windows")
        sys.exit(1)
    
    success = update_env_file(instrument)
    if success:
        print(f"\nSUCCESS: Configuration updated! Restart system to use {instrument}.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

