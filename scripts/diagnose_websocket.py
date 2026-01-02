"""Diagnose WebSocket connection and data reception."""

import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from kiteconnect import KiteConnect, KiteTicker
from data.market_memory import MarketMemory

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Track connection status
connected = False
tick_received = False
tick_count = 0
error_occurred = None

def on_ticks(ws, ticks):
    global tick_received, tick_count
    tick_received = True
    tick_count += len(ticks)
    for tick in ticks[:3]:  # Log first 3 ticks
        logger.info(f"TICK RECEIVED: Token={tick.get('instrument_token')}, Price={tick.get('last_price')}, Volume={tick.get('volume')}")

def on_connect(ws, response):
    global connected
    connected = True
    logger.info(f"WEBSOCKET CONNECTED: {response}")
    
    # Get instrument token and subscribe
    creds = json.load(open("credentials.json"))
    kite = KiteConnect(api_key=creds["api_key"])
    kite.set_access_token(creds["access_token"])
    
    instruments = kite.instruments("NSE")
    token = None
    for inst in instruments:
        if inst["tradingsymbol"] == "NIFTY BANK":
            token = inst["instrument_token"]
            break
    
    if token:
        ws.subscribe([token])
        ws.set_mode(ws.MODE_FULL, [token])
        logger.info(f"SUBSCRIBED to token: {token}")
    else:
        logger.error("Could not find Bank Nifty token")

def on_close(ws, code, reason):
    global connected
    connected = False
    logger.warning(f"WEBSOCKET CLOSED: {code} - {reason}")

def on_error(ws, code, reason):
    global error_occurred
    error_occurred = f"{code} - {reason}"
    logger.error(f"WEBSOCKET ERROR: {code} - {reason}")

def main():
    logger.info("=" * 60)
    logger.info("WebSocket Diagnostic Test")
    logger.info("=" * 60)
    
    # Load credentials
    creds = json.load(open("credentials.json"))
    kite = KiteConnect(api_key=creds["api_key"])
    kite.set_access_token(creds["access_token"])
    logger.info("Kite Connect initialized")
    
    # Initialize WebSocket
    ticker = KiteTicker(creds["api_key"], creds["access_token"])
    ticker.on_ticks = on_ticks
    ticker.on_connect = on_connect
    ticker.on_close = on_close
    ticker.on_error = on_error
    
    logger.info("Connecting to WebSocket...")
    ticker.connect(threaded=True)
    
    # Wait for connection
    logger.info("Waiting for connection (max 10 seconds)...")
    for i in range(10):
        if connected:
            break
        if error_occurred:
            logger.error(f"Connection failed: {error_occurred}")
            return
        time.sleep(1)
    
    if not connected:
        logger.error("WebSocket did not connect within 10 seconds")
        return
    
    logger.info("=" * 60)
    logger.info("WebSocket connected! Waiting for ticks...")
    logger.info("=" * 60)
    
    # Wait for ticks
    for i in range(30):  # Wait 30 seconds
        if tick_received:
            logger.info(f"SUCCESS! Received {tick_count} ticks")
            break
        time.sleep(1)
        if i % 5 == 0:
            logger.info(f"Waiting for ticks... ({i}/30 seconds)")
    
    if not tick_received:
        logger.warning("No ticks received after 30 seconds")
        logger.warning("Possible reasons:")
        logger.warning("  1. Market is closed")
        logger.warning("  2. WebSocket subscription failed")
        logger.warning("  3. No market data available")
    else:
        logger.info(f"Total ticks received: {tick_count}")
    
    ticker.close()
    logger.info("Diagnostic complete")

if __name__ == "__main__":
    main()

