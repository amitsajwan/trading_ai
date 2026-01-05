"""Shim to preserve top-level `populate_demo_data` while implementation lives in `data_niftybank` module."""

from data_niftybank.tools.populate_demo_data import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def populate_historical_data():
    """Fetch and store historical Bitcoin data."""
    from data.binance_spot_fetcher import BinanceSpotFetcher
    import requests
    
    logger.info("Fetching historical Bitcoin data from Binance...")
    
    # Get historical klines (OHLC data) from Binance REST API
    symbol = "BTCUSDT"
    interval = "1h"  # 1 hour candles
    limit = 168  # Last 7 days (24 * 7)
    
    url = f"https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    
    response = requests.get(url, params=params)
    klines = response.json()
    
    # Store in MongoDB
    mongo_client = get_mongo_client()
    db = mongo_client[settings.mongodb_db_name]
    ohlc_collection = get_collection(db, "ohlc_history")
    
    logger.info(f"Storing {len(klines)} hourly candles to MongoDB...")
    
    for kline in klines:
        timestamp = datetime.fromtimestamp(kline[0] / 1000)
        
        ohlc_doc = {
            "instrument": "BTC-USD",
            "timestamp": timestamp,
            "open": float(kline[1]),
            "high": float(kline[2]),
            "low": float(kline[3]),
            "close": float(kline[4]),
            "volume": float(kline[5]),
            "interval": "1h"
        }
        
        ohlc_collection.update_one(
            {"instrument": "BTC-USD", "timestamp": timestamp, "interval": "1h"},
            {"$set": ohlc_doc},
            upsert=True
        )
    
    logger.info(f"✅ Stored {len(klines)} historical candles")
    return len(klines)


async def create_demo_trades():
    """Create some demo trades for testing."""
    import uuid
    mongo_client = get_mongo_client()
    db = mongo_client[settings.mongodb_db_name]
    trades_collection = get_collection(db, "trades_executed")
    
    logger.info("Creating demo trades...")
    
    # Clear existing trades to avoid duplicates
    trades_collection.delete_many({})
    
    now = datetime.now()
    demo_trades = [
        {
            "trade_id": str(uuid.uuid4()),
            "instrument": "BTC-USD",
            "entry_timestamp": now - timedelta(hours=24),
            "entry_price": 90500.0,
            "exit_timestamp": now - timedelta(hours=20),
            "exit_price": 91200.0,
            "quantity": 0.1,
            "pnl": 70.0,
            "status": "CLOSED",
            "side": "BUY"
        },
        {
            "trade_id": str(uuid.uuid4()),
            "instrument": "BTC-USD",
            "entry_timestamp": now - timedelta(hours=18),
            "entry_price": 91000.0,
            "exit_timestamp": now - timedelta(hours=15),
            "exit_price": 90200.0,
            "quantity": 0.1,
            "pnl": -80.0,
            "status": "CLOSED",
            "side": "BUY"
        },
        {
            "trade_id": str(uuid.uuid4()),
            "instrument": "BTC-USD",
            "entry_timestamp": now - timedelta(hours=12),
            "entry_price": 90800.0,
            "exit_timestamp": now - timedelta(hours=8),
            "exit_price": 91500.0,
            "quantity": 0.15,
            "pnl": 105.0,
            "status": "CLOSED",
            "side": "BUY"
        },
        {
            "trade_id": str(uuid.uuid4()),
            "instrument": "BTC-USD",
            "entry_timestamp": now - timedelta(hours=6),
            "entry_price": 91300.0,
            "exit_timestamp": now - timedelta(hours=3),
            "exit_price": 91800.0,
            "quantity": 0.12,
            "pnl": 60.0,
            "status": "CLOSED",
            "side": "BUY"
        },
        {
            "trade_id": str(uuid.uuid4()),
            "instrument": "BTC-USD",
            "entry_timestamp": now - timedelta(hours=2),
            "entry_price": 91600.0,
            "quantity": 0.1,
            "pnl": 0.0,
            "status": "OPEN",
            "side": "BUY"
        }
    ]
    
    for trade in demo_trades:
        trades_collection.insert_one(trade)
    
    logger.info(f"✅ Created {len(demo_trades)} demo trades (4 closed, 1 open)")
    return len(demo_trades)


async def start_live_feed(duration_seconds=60):
    """Start live Bitcoin data feed for testing."""
    logger.info(f"Starting live Bitcoin feed for {duration_seconds} seconds...")
    
    # Initialize market memory
    market_memory = MarketMemory()
    
    # Create and start crypto data feed
    crypto_feed = CryptoDataFeed(market_memory)
    
    # Start the feed
    await crypto_feed.start()
    
    logger.info("✅ Live Bitcoin feed started - data streaming to Redis & MongoDB")
    logger.info("📊 Dashboard at http://localhost:8000 should now show real-time data!")
    
    # Run for specified duration
    try:
        await asyncio.sleep(duration_seconds)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Stopping feed...")
    
    # Stop the feed
    await crypto_feed.stop()
    logger.info("✅ Feed stopped")


async def main():
    """Main entry point."""
    logger.info("=" * 70)
    logger.info("BITCOIN DEMO DATA POPULATOR")
    logger.info("=" * 70)
    
    try:
        # Step 1: Populate historical data
        logger.info("\n📊 Step 1: Loading historical Bitcoin data...")
        candles_count = await populate_historical_data()
        
        # Step 2: Create demo trades
        logger.info("\n💰 Step 2: Creating demo trades...")
        trades_count = await create_demo_trades()
        
        # Step 3: Start live feed
        logger.info("\n🔴 Step 3: Starting live Bitcoin feed...")
        logger.info("Press Ctrl+C to stop the live feed")
        await start_live_feed(duration_seconds=300)  # Run for 5 minutes
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ DEMO DATA POPULATED SUCCESSFULLY")
        logger.info(f"   - {candles_count} historical candles loaded")
        logger.info(f"   - {trades_count} demo trades created")
        logger.info("   - Live feed ran for 5 minutes")
        logger.info("\n🌐 Open http://localhost:8000 to see the dashboard with live data!")
        logger.info("=" * 70)
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Operation cancelled by user")
    except Exception as e:
        logger.error(f"\n❌ Error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
