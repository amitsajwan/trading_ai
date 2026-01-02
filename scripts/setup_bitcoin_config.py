"""Setup script to configure system for Bitcoin trading."""

import os
from pathlib import Path

def update_env_for_bitcoin():
    """Update .env file with Bitcoin configuration."""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("Creating .env file...")
        content = ""
    else:
        content = env_file.read_text(encoding='utf-8')
    
    lines = content.split('\n')
    updated_lines = []
    bitcoin_config_added = False
    
    # Bitcoin configuration
    bitcoin_config = {
        'INSTRUMENT_SYMBOL': 'BTC-USD',
        'INSTRUMENT_NAME': 'Bitcoin',
        'INSTRUMENT_EXCHANGE': 'CRYPTO',
        'DATA_SOURCE': 'CRYPTO',
        'NEWS_QUERY': 'Bitcoin OR BTC OR cryptocurrency',
        'NEWS_KEYWORDS': 'Bitcoin,BTC,cryptocurrency,crypto',
        'MACRO_DATA_ENABLED': 'false',
        'MARKET_24_7': 'true',
        'MARKET_OPEN_TIME': '00:00:00',
        'MARKET_CLOSE_TIME': '23:59:59',
    }
    
    # Update or add each config
    for line in lines:
        updated = False
        for key, value in bitcoin_config.items():
            if line.startswith(f'{key}='):
                updated_lines.append(f'{key}={value}')
                updated = True
                bitcoin_config_added = True
                break
        if not updated:
            updated_lines.append(line)
    
    # Add missing configs
    for key, value in bitcoin_config.items():
        if not any(line.startswith(f'{key}=') for line in updated_lines):
            updated_lines.append(f'{key}={value}')
            bitcoin_config_added = True
    
    # Add section header if config was added
    if bitcoin_config_added and not any('# Bitcoin Configuration' in line for line in updated_lines):
        # Find insertion point (before existing config or at end)
        insert_idx = len(updated_lines)
        for i, line in enumerate(updated_lines):
            if line.startswith('#') and ('Instrument' in line or 'Market' in line):
                insert_idx = i
                break
        
        updated_lines.insert(insert_idx, '')
        updated_lines.insert(insert_idx, '# Bitcoin Configuration')
    
    env_file.write_text('\n'.join(updated_lines), encoding='utf-8')
    print("Bitcoin configuration added/updated in .env")
    print("\nConfiguration:")
    for key, value in bitcoin_config.items():
        print(f"  {key}={value}")
    print("\nNote: You'll need to configure a crypto data source API (Binance, Coinbase, etc.)")
    print("      Add DATA_SOURCE_API_KEY and DATA_SOURCE_SECRET to .env")

if __name__ == "__main__":
    update_env_for_bitcoin()

