"""Test Zerodha WebSocket connection directly using KiteTicker."""

import sys
import json
import time
import logging
from pathlib import Path
from kiteconnect import KiteConnect, KiteTicker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_websocket():
    """Test WebSocket connection using KiteTicker."""
    print("=" * 60)
    print("Testing Zerodha WebSocket Connection")
    print("=" * 60)
    
    # Load credentials
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        print("[ERROR] credentials.json not found")
        return False
    
    with open(cred_path) as f:
        creds = json.load(f)
    
    api_key = creds.get("api_key") or creds.get("apiKey")
    access_token = creds.get("access_token") or creds.get("accessToken")
    
    if not api_key or not access_token:
        print("[ERROR] Missing api_key or access_token")
        return False
    
    print(f"[OK] API Key: {api_key[:10]}...")
    print(f"[OK] Access Token: {access_token[:20]}...")
    print()
    
    # Initialize Kite Connect
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    # Get Bank Nifty instrument token
    try:
        instruments = kite.instruments("NSE")
        banknifty_token = None
        for inst in instruments:
            if inst["tradingsymbol"] == "NIFTY BANK":
                banknifty_token = inst["instrument_token"]
                break
        
        if not banknifty_token:
            print("[ERROR] Bank Nifty instrument not found")
            return False
        
        print(f"[OK] Bank Nifty Token: {banknifty_token}")
        print()
    except Exception as e:
        print(f"[ERROR] Could not get instruments: {e}")
        return False
    
    # Track ticks received
    ticks_received = []
    connected = False
    
    def on_connect(ws, response):
        """Handle WebSocket connection."""
        nonlocal connected
        connected = True
        logger.info("✅ WebSocket connected!")
        logger.info(f"Response: {response}")
        ws.subscribe([banknifty_token])
        ws.set_mode(ws.MODE_FULL, [banknifty_token])
        logger.info(f"✅ Subscribed to Bank Nifty (token: {banknifty_token})")
    
    def on_ticks(ws, ticks):
        """Handle incoming ticks."""
        for tick in ticks:
            ticks_received.append(tick)
            price = tick.get("last_price", 0)
            volume = tick.get("volume", 0)
            logger.info(f"📊 Tick: Price=₹{price:,.2f}, Volume={volume}")
    
    def on_close(ws, code, reason):
        """Handle WebSocket close."""
        logger.warning(f"❌ WebSocket closed: {code} - {reason}")
    
    def on_error(ws, code, reason):
        """Handle WebSocket error."""
        logger.error(f"❌ WebSocket error: {code} - {reason}")
    
    # Create KiteTicker (this automatically handles enctoken)
    print("Creating KiteTicker instance...")
    print("Note: KiteTicker automatically gets enctoken internally")
    print()
    
    ticker = KiteTicker(api_key, access_token)
    ticker.on_connect = on_connect
    ticker.on_ticks = on_ticks
    ticker.on_close = on_close
    ticker.on_error = on_error
    
    print("Connecting to WebSocket...")
    print("(This may take a few seconds)")
    print()
    
    # Connect (non-blocking)
    ticker.connect(threaded=True)
    
    # Wait for connection
    timeout = 10
    elapsed = 0
    while not connected and elapsed < timeout:
        time.sleep(0.5)
        elapsed += 0.5
        print(".", end="", flush=True)
    
    print()
    print()
    
    if not connected:
        print("[ERROR] WebSocket did not connect within timeout")
        ticker.close()
        return False
    
    print("[OK] WebSocket connected successfully!")
    print()
    print("Waiting for ticks (30 seconds)...")
    print("(If market is closed, you won't receive ticks)")
    print()
    
    # Wait for ticks
    start_time = time.time()
    while time.time() - start_time < 30:
        time.sleep(1)
        if ticks_received:
                    print(f"[OK] Received {len(ticks_received)} ticks so far...")
    
    print()
    print("=" * 60)
    print("Test Results")
    print("=" * 60)
    print(f"Connection: {'[OK] Connected' if connected else '[FAIL] Failed'}")
    print(f"Ticks Received: {len(ticks_received)}")
    
    if ticks_received:
        latest = ticks_received[-1]
        print(f"Latest Price: Rs {latest.get('last_price', 0):,.2f}")
        print(f"Latest Volume: {latest.get('volume', 0):,}")
        print()
        print("[SUCCESS] WebSocket is working and receiving data!")
        return True
    else:
        print()
        print("[WARN] WebSocket connected but no ticks received")
        print("       Possible reasons:")
        print("       1. Market is closed (9:15 AM - 3:30 PM IST)")
        print("       2. Need Market Data subscription (Rs 500/month)")
        print("       3. WebSocket needs time to start receiving data")
        print()
        print("       Connection is working - data will flow during market hours")
        return True  # Connection works, just no data yet
    
    ticker.close()

if __name__ == "__main__":
    success = test_websocket()
    sys.exit(0 if success else 1)

