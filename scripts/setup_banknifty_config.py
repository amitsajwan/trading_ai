"""Setup script to configure system for Bank Nifty trading (default)."""

import os
from pathlib import Path

def update_env_for_banknifty():
    """Update .env file with Bank Nifty configuration."""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("Creating .env file...")
        content = ""
    else:
        content = env_file.read_text(encoding='utf-8')
    
    lines = content.split('\n')
    updated_lines = []
    config_added = False
    
    # Bank Nifty configuration
    banknifty_config = {
        'INSTRUMENT_SYMBOL': 'NIFTY BANK',
        'INSTRUMENT_NAME': 'Bank Nifty',
        'INSTRUMENT_EXCHANGE': 'NSE',
        'DATA_SOURCE': 'ZERODHA',
        'NEWS_QUERY': 'Bank Nifty OR banking sector OR RBI',
        'NEWS_KEYWORDS': 'Bank Nifty,banking sector,RBI',
        'MACRO_DATA_ENABLED': 'true',
        'MARKET_24_7': 'false',
        'MARKET_OPEN_TIME': '09:15:00',
        'MARKET_CLOSE_TIME': '15:30:00',
    }
    
    # Update or add each config
    for line in lines:
        updated = False
        for key, value in banknifty_config.items():
            if line.startswith(f'{key}='):
                updated_lines.append(f'{key}={value}')
                updated = True
                config_added = True
                break
        if not updated:
            updated_lines.append(line)
    
    # Add missing configs
    for key, value in banknifty_config.items():
        if not any(line.startswith(f'{key}=') for line in updated_lines):
            updated_lines.append(f'{key}={value}')
            config_added = True
    
    # Add section header if config was added
    if config_added and not any('# Bank Nifty Configuration' in line for line in updated_lines):
        insert_idx = len(updated_lines)
        for i, line in enumerate(updated_lines):
            if line.startswith('#') and ('Instrument' in line or 'Market' in line):
                insert_idx = i
                break
        
        updated_lines.insert(insert_idx, '')
        updated_lines.insert(insert_idx, '# Bank Nifty Configuration')
    
    env_file.write_text('\n'.join(updated_lines), encoding='utf-8')
    print("Bank Nifty configuration added/updated in .env")
    print("\nConfiguration:")
    for key, value in banknifty_config.items():
        print(f"  {key}={value}")

if __name__ == "__main__":
    update_env_for_banknifty()

