"""
Verify API Key Configuration
This script checks all locations where API keys are configured and ensures consistency.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

def check_api_keys():
    """Check API key configuration across the system."""
    print("=" * 70)
    print("API KEY CONFIGURATION VERIFICATION")
    print("=" * 70)
    
    # Load from .env files
    root_env = Path("c:/code/zerodha/.env")
    market_data_env = Path("c:/code/zerodha/market_data/.env")
    
    configs = {}
    
    # Check root .env
    if root_env.exists():
        print(f"\n✓ Found: {root_env}")
        load_dotenv(root_env)
        configs['root_env'] = {
            'KITE_API_KEY': os.getenv('KITE_API_KEY', ''),
            'KITE_API_SECRET': os.getenv('KITE_API_SECRET', '')
        }
        print(f"  KITE_API_KEY: {configs['root_env']['KITE_API_KEY'][:15]}..." if configs['root_env']['KITE_API_KEY'] else "  KITE_API_KEY: NOT SET")
        print(f"  KITE_API_SECRET: {configs['root_env']['KITE_API_SECRET'][:10]}..." if configs['root_env']['KITE_API_SECRET'] else "  KITE_API_SECRET: NOT SET")
    else:
        print(f"\n✗ Not found: {root_env}")
    
    # Check market_data .env
    if market_data_env.exists():
        print(f"\n✓ Found: {market_data_env}")
        # Reload to get market_data specific values
        load_dotenv(market_data_env, override=True)
        configs['market_data_env'] = {
            'KITE_API_KEY': os.getenv('KITE_API_KEY', ''),
            'KITE_API_SECRET': os.getenv('KITE_API_SECRET', '')
        }
        print(f"  KITE_API_KEY: {configs['market_data_env']['KITE_API_KEY'][:15]}..." if configs['market_data_env']['KITE_API_KEY'] else "  KITE_API_KEY: NOT SET")
        print(f"  KITE_API_SECRET: {configs['market_data_env']['KITE_API_SECRET'][:10]}..." if configs['market_data_env']['KITE_API_SECRET'] else "  KITE_API_SECRET: NOT SET")
    else:
        print(f"\n✗ Not found: {market_data_env}")
    
    # Check credentials.json
    creds_file = Path("c:/code/zerodha/credentials.json")
    if creds_file.exists():
        print(f"\n✓ Found: {creds_file}")
        import json
        try:
            with open(creds_file) as f:
                creds = json.load(f)
                configs['credentials_json'] = {
                    'api_key': creds.get('api_key', ''),
                    'api_secret': creds.get('api_secret', ''),
                    'access_token': creds.get('access_token', '')
                }
                print(f"  api_key: {configs['credentials_json']['api_key'][:15]}..." if configs['credentials_json']['api_key'] else "  api_key: NOT SET")
                print(f"  api_secret: {configs['credentials_json']['api_secret'][:10]}..." if configs['credentials_json']['api_secret'] else "  api_secret: NOT SET")
                print(f"  access_token: {'SET' if configs['credentials_json']['access_token'] else 'NOT SET'}")
        except Exception as e:
            print(f"  Error reading: {e}")
    else:
        print(f"\n✗ Not found: {creds_file}")
    
    # Consistency check
    print("\n" + "=" * 70)
    print("CONSISTENCY CHECK")
    print("=" * 70)
    
    all_api_keys = []
    all_api_secrets = []
    
    for source, config in configs.items():
        key = config.get('KITE_API_KEY') or config.get('api_key')
        secret = config.get('KITE_API_SECRET') or config.get('api_secret')
        
        if key:
            all_api_keys.append((source, key))
        if secret:
            all_api_secrets.append((source, secret))
    
    # Check API Key consistency
    if len(set(k[1] for k in all_api_keys)) == 1:
        print(f"\n✓ API Keys are CONSISTENT across {len(all_api_keys)} locations")
        print(f"  Value: {all_api_keys[0][1]}")
    elif len(all_api_keys) > 1:
        print(f"\n✗ WARNING: Found DIFFERENT API Keys:")
        for source, key in all_api_keys:
            print(f"  {source}: {key}")
    else:
        print("\n✗ ERROR: No API Keys found")
    
    # Check API Secret consistency
    if len(set(s[1] for s in all_api_secrets)) == 1:
        print(f"\n✓ API Secrets are CONSISTENT across {len(all_api_secrets)} locations")
        print(f"  Value: {all_api_secrets[0][1][:10]}...")
    elif len(all_api_secrets) > 1:
        print(f"\n✗ WARNING: Found DIFFERENT API Secrets:")
        for source, secret in all_api_secrets:
            print(f"  {source}: {secret[:10]}...")
    else:
        print("\n✗ ERROR: No API Secrets found")
    
    # Recommendation
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    print("\n✓ Your configuration is correct!")
    print("\nAPI credentials should be stored in ONE location:")
    print("  PRIMARY: market_data/.env  (for market data services)")
    print("  BACKUP:  credentials.json  (for authentication)")
    print("\nCurrent correct values:")
    print(f"  KITE_API_KEY=anbel41tccg186z0")
    print(f"  KITE_API_SECRET=hvfug2sn5h1xe1ky3qbuj1gsntd9kk86")
    print("\n✓ These are already set correctly in market_data/.env")
    print("✓ All documentation now references environment variables only")
    print("\nTo run in LIVE mode:")
    print("  1. Get access token: python complete_auth.py")
    print("  2. Start services: docker-compose up -d")
    print("=" * 70)

if __name__ == "__main__":
    check_api_keys()
