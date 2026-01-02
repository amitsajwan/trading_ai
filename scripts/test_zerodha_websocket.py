"""Test Zerodha WebSocket connection."""

import json
import logging
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kiteconnect import KiteConnect, KiteTicker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_kite_credentials() -> dict:
    """Load Kite credentials from credentials.json."""
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        raise FileNotFoundError("credentials.json not found. Run auto_login.py first.")
    
    with open(cred_path) as f:
        return json.load(f)


def get_instrument_token(kite: KiteConnect) -> int:
    """Get Bank Nifty instrument token."""
    try:
        instruments = kite.instruments("NSE")
        
        # Find Bank Nifty
        for inst in instruments:
            if inst["tradingsymbol"] == "NIFTY BANK" or inst["name"] == "NIFTY BANK":
                logger.info(f"Found Bank Nifty: {inst['tradingsymbol']} - Token: {inst['instrument_token']}")
                return inst["instrument_token"]
        
        logger.error("Could not find Bank Nifty instrument")
        return None
    except Exception as e:
        logger.error(f"Error getting instrument token: {e}")
        return None


# Global variables for callbacks
tick_count = 0
connected = False
error_occurred = None


def on_ticks(ws, ticks):
    """Handle incoming ticks."""
    global tick_count
    for tick in ticks:
        tick_count += 1
        instrument_token = tick.get("instrument_token")
        last_price = tick.get("last_price", 0.0)
        volume = tick.get("volume", 0)
        logger.info(f"Tick #{tick_count}: Token={instrument_token}, Price={last_price}, Volume={volume}")


def on_connect(ws, response):
    """Handle WebSocket connection."""
    global connected
    connected = True
    logger.info(f"✅ WebSocket connected! Response: {response}")
    
    # Get instrument token
    creds = load_kite_credentials()
    kite = KiteConnect(api_key=creds["api_key"])
    kite.set_access_token(creds["access_token"])
    
    instrument_token = get_instrument_token(kite)
    if instrument_token:
        ws.subscribe([instrument_token])
        ws.set_mode(ws.MODE_FULL, [instrument_token])
        logger.info(f"✅ Subscribed to Bank Nifty (token: {instrument_token})")
    else:
        logger.error("❌ Could not find instrument token")


def on_close(ws, code, reason):
    """Handle WebSocket close."""
    global connected
    connected = False
    logger.warning(f"❌ WebSocket closed: {code} - {reason}")


def on_error(ws, code, reason):
    """Handle WebSocket error."""
    global error_occurred
    error_occurred = f"{code} - {reason}"
    logger.error(f"❌ WebSocket error: {code} - {reason}")


def main():
    """Test WebSocket connection."""
    logger.info("=" * 60)
    logger.info("Testing Zerodha WebSocket Connection")
    logger.info("=" * 60)
    
    try:
        # Load credentials
        creds = load_kite_credentials()
        logger.info("✅ Credentials loaded")
        
        # Initialize Kite Connect
        kite = KiteConnect(api_key=creds["api_key"])
        kite.set_access_token(creds["access_token"])
        logger.info("✅ Kite Connect initialized")
        
        # Test API connection
        try:
            profile = kite.profile()
            logger.info(f"✅ API connection working - User: {profile.get('user_name', 'Unknown')}")
        except Exception as e:
            logger.error(f"❌ API connection failed: {e}")
            return
        
        # Get instrument token
        instrument_token = get_instrument_token(kite)
        if not instrument_token:
            logger.error("❌ Could not get instrument token")
            return
        
        # Initialize WebSocket
        logger.info("Initializing WebSocket...")
        ticker = KiteTicker(creds["api_key"], creds["access_token"])
        
        # Set callbacks
        ticker.on_ticks = on_ticks
        ticker.on_connect = on_connect
        ticker.on_close = on_close
        ticker.on_error = on_error
        
        # Connect
        logger.info("Connecting to WebSocket...")
        ticker.connect(threaded=True)
        
        # Wait for connection
        logger.info("Waiting for connection...")
        for i in range(10):
            if connected:
                break
            if error_occurred:
                logger.error(f"Connection error: {error_occurred}")
                return
            time.sleep(1)
            logger.info(f"Waiting... ({i+1}/10)")
        
        if not connected:
            logger.error("❌ WebSocket did not connect within 10 seconds")
            ticker.close()
            return
        
        # Wait for ticks
        logger.info("=" * 60)
        logger.info("WebSocket connected! Waiting for ticks...")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)
        
        try:
            for i in range(60):  # Wait up to 60 seconds for ticks
                if error_occurred:
                    logger.error(f"Error occurred: {error_occurred}")
                    break
                if not connected:
                    logger.warning("Connection lost")
                    break
                if tick_count > 0:
                    logger.info(f"✅ Receiving data! Total ticks: {tick_count}")
                    break
                time.sleep(1)
            
            if tick_count == 0:
                logger.warning("⚠️  No ticks received after 60 seconds")
                logger.warning("This might be normal if market is closed")
            
        except KeyboardInterrupt:
            logger.info("\nStopping...")
        finally:
            ticker.close()
            logger.info("✅ WebSocket closed")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    main()

