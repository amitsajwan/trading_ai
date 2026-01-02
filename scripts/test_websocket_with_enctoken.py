"""Test Zerodha WebSocket with manually provided enctoken."""

import sys
import json
import time
import logging
import urllib.parse
from pathlib import Path
try:
    import websocket
except ImportError:
    print("Please install websocket-client: pip install websocket-client")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_websocket_with_enctoken(enctoken: str, user_id: str, api_key: str = "kitefront"):
    """Test WebSocket connection with enctoken."""
    print("=" * 60)
    print("Testing Zerodha WebSocket with enctoken")
    print("=" * 60)
    
    # Construct WebSocket URL (same format as browser)
    ws_url = (
        f"wss://ws.zerodha.com/"
        f"?api_key={api_key}"
        f"&user_id={user_id}"
        f"&enctoken={urllib.parse.quote(enctoken)}"
        f"&uid={int(time.time() * 1000)}"
        f"&user-agent=kite3-web"
        f"&version=3.0.0"
    )
    
    print(f"[OK] User ID: {user_id}")
    print(f"[OK] enctoken: {enctoken[:30]}...")
    print()
    print("Connecting to WebSocket...")
    print()
    
    ticks_received = []
    connected = False
    
    def on_message(ws, message):
        """Handle WebSocket messages."""
        try:
            # Zerodha sends binary messages for ticks
            if isinstance(message, bytes):
                # Parse binary tick data
                # Format: [token, ltp, volume, ...]
                import struct
                if len(message) >= 20:  # Minimum size for tick data
                    # This is a simplified parser - actual format may vary
                    ticks_received.append(message)
                    logger.info(f"📊 Received binary tick data ({len(message)} bytes)")
            else:
                # Text message (meta, errors, etc.)
                logger.info(f"📨 Message: {message[:200]}")
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
    
    def on_error(ws, error):
        """Handle WebSocket errors."""
        error_str = str(error)
        if "Invalid" in error_str or "400" in error_str:
            logger.error(f"❌ WebSocket error: Invalid enctoken (token may have expired)")
            logger.error(f"   Enctokens expire frequently. Please extract a fresh one from browser.")
        else:
            logger.error(f"❌ WebSocket error: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        logger.warning(f"❌ WebSocket closed: {close_status_code} - {close_msg}")
    
    def on_open(ws):
        """Handle WebSocket open."""
        nonlocal connected
        connected = True
        logger.info("✅ WebSocket connected!")
        
        # Subscribe to Bank Nifty (token: 260105)
        # Format: {"a": "subscribe", "v": [260105]}
        subscribe_msg = json.dumps({
            "a": "subscribe",
            "v": [260105]  # Bank Nifty token
        })
        ws.send(subscribe_msg)
        logger.info("✅ Subscribed to Bank Nifty (token: 260105)")
    
    # Create WebSocket connection
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    
    # Run in background thread
    import threading
    ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
    ws_thread.start()
    
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
        print("[ERROR] WebSocket did not connect")
        ws.close()
        return False
    
    print("[OK] WebSocket connected!")
    print("Waiting for ticks (30 seconds)...")
    print()
    
    # Wait for ticks
    start_time = time.time()
    while time.time() - start_time < 30:
        time.sleep(1)
        if ticks_received:
            print(f"✅ Received {len(ticks_received)} messages...")
    
    print()
    print("=" * 60)
    print("Test Results")
    print("=" * 60)
    print(f"Connection: {'✅ Connected' if connected else '❌ Failed'}")
    print(f"Messages Received: {len(ticks_received)}")
    
    ws.close()
    
    if ticks_received:
        print()
        print("[SUCCESS] WebSocket is working! ✅")
        return True
    else:
        print()
        print("[WARN] Connected but no tick data received")
        print("       This might be normal if market is closed")
        return True

def main():
    """Main entry point."""
    import sys
    
    print("=" * 60)
    print("Zerodha WebSocket Test with enctoken")
    print("=" * 60)
    print()
    
    # Get enctoken from command line or input
    if len(sys.argv) > 1:
        enctoken = sys.argv[1].strip()
        print(f"[OK] Using enctoken from command line")
    else:
        print("To get enctoken:")
        print("  1. Open Zerodha Kite in browser")
        print("  2. Open DevTools (F12)")
        print("  3. Go to Network tab -> Filter by WS")
        print("  4. Find WebSocket to ws.zerodha.com")
        print("  5. Copy enctoken from URL")
        print()
        print("Usage: python scripts/test_websocket_with_enctoken.py <enctoken>")
        print("   OR: python scripts/test_websocket_with_enctoken.py")
        print("       (will prompt for enctoken)")
        print()
        
        try:
            enctoken = input("Enter enctoken (or press Enter to skip): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("Skipping test. To test:")
            print("  python scripts/test_websocket_with_enctoken.py <enctoken>")
            return
        
        if not enctoken:
            print()
            print("Skipping test. To test:")
            print("  python scripts/test_websocket_with_enctoken.py <enctoken>")
            return
    
    # Get user_id from credentials
    cred_path = Path("credentials.json")
    if cred_path.exists():
        with open(cred_path) as f:
            creds = json.load(f)
        user_id = creds.get("user_id") or creds.get("userId") or "BV2032"
    else:
        user_id = input("Enter user_id (e.g., BV2032): ").strip()
    
    if not user_id:
        print("[ERROR] user_id required")
        return
    
    test_websocket_with_enctoken(enctoken, user_id)

if __name__ == "__main__":
    main()

