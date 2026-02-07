#!/usr/bin/env python3
"""
Complete Zerodha Authentication Flow

This script securely handles the complete Zerodha authentication flow:
1. Loads API credentials from environment variables or .env files
2. Uses a valid request token to obtain an access token
3. Saves credentials securely to credentials.json

⚠️ SECURITY NOTE: Never commit hardcoded API keys, request tokens, or secrets to version control!
   Load credentials from environment variables or config files instead.

Usage:
    python complete_auth.py

Required environment variables:
    KITE_API_KEY         - Your Zerodha API key
    KITE_API_SECRET      - Your Zerodha API secret
    KITE_REQUEST_TOKEN   - Request token from login flow (valid for ~5 minutes)
"""

import os
import json
import sys
from pathlib import Path
from kiteconnect import KiteConnect

def load_config():
    """Load configuration from environment or config files."""
    # Try loading from environment first
    api_key = os.getenv('KITE_API_KEY', '').strip()
    api_secret = os.getenv('KITE_API_SECRET', '').strip()
    request_token = os.getenv('KITE_REQUEST_TOKEN', '').strip()
    
    # If not in environment, try .env file
    if not api_key or not api_secret or not request_token:
        try:
            from dotenv import load_dotenv
            load_dotenv('.env')
            api_key = api_key or os.getenv('KITE_API_KEY', '').strip()
            api_secret = api_secret or os.getenv('KITE_API_SECRET', '').strip()
            request_token = request_token or os.getenv('KITE_REQUEST_TOKEN', '').strip()
        except ImportError:
            pass
    
    return api_key, api_secret, request_token

def complete_auth():
    """Complete the authentication flow and save credentials."""
    print("🔐 Zerodha Authentication - Complete Flow")
    print("="*70)
    
    # Load configuration
    api_key, api_secret, request_token = load_config()
    
    # Validate we have all required credentials
    if not api_key:
        print("❌ ERROR: KITE_API_KEY not found in environment")
        print("\n   Set it with: export KITE_API_KEY='your_api_key'")
        return False
    
    if not api_secret:
        print("❌ ERROR: KITE_API_SECRET not found in environment")
        print("\n   Set it with: export KITE_API_SECRET='your_api_secret'")
        return False
    
    if not request_token:
        print("❌ ERROR: KITE_REQUEST_TOKEN not found in environment")
        print("\n   Request token is obtained from the login flow at:")
        print("   https://kite.zerodha.com/api/login")
        print("\n   Set it with: export KITE_REQUEST_TOKEN='your_request_token'")
        return False
    
    print(f"✅ Configuration loaded:")
    print(f"   API Key: {api_key[:10]}...{api_key[-5:]}")
    print(f"   Request Token: {request_token[:10]}...{request_token[-5:]}")
    
    print("\n🔄 Exchanging request token for access token...")
    try:
        kite = KiteConnect(api_key=api_key)
        session = kite.generate_session(request_token, api_secret=api_secret)
        
        print(f"✅ Session generated!")
        print(f"   Access Token: {session['access_token'][:25]}...")
        print(f"   User ID: {session['user_id']}")
        
        # Save to credentials.json - convert datetime to string
        session_to_save = {}
        for k, v in session.items():
            if hasattr(v, 'isoformat'):  # datetime object
                session_to_save[k] = v.isoformat()
            else:
                session_to_save[k] = v
        
        with open('credentials.json', 'w') as f:
            json.dump(session_to_save, f, indent=2)
        print(f"✅ Saved to credentials.json")
        
        # Also try Redis
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            r.set('kite:access_token', session['access_token'])
            r.set('kite:user_id', session['user_id'])
            print(f"✅ Saved to Redis")
        except Exception as e:
            print(f"⚠️  Redis not available (will use file): {e}")
        
        print("\n✅ Authentication complete!")
        print("\n🎉 You're ready to start the application:")
        print("   python start_unified.py --live")
        
        # Update environment for current session
        os.environ['KITE_API_KEY'] = api_key
        os.environ['KITE_ACCESS_TOKEN'] = session['access_token']
        os.environ['KITE_USER_ID'] = session['user_id']
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        if "Invalid request token" in str(e) or "401" in str(e):
            print("\n💡 Request token invalid or expired (valid for ~5 minutes)")
            print("   Get a new one from: https://kite.zerodha.com/api/login")
        
        return False

if __name__ == "__main__":
    success = complete_auth()
    sys.exit(0 if success else 1)

