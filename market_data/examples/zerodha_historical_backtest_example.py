"""Example: Historical backtesting using Zerodha API.

This demonstrates how to fetch historical data directly from Zerodha
and run backtests using the same code path as live trading.
"""

import asyncio
import logging
import os
from datetime import date, timedelta
from dotenv import load_dotenv

from kiteconnect import KiteConnect

from market_data.src.market_data.store import InMemoryMarketStore
from market_data.src.market_data.adapters.unified_data_flow import UnifiedDataFlow
from market_data.src.market_data.adapters.paper_broker import PaperBroker
from market_data.src.market_data.contracts import OHLCBar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def simple_strategy_on_candle(candle: OHLCBar, broker: PaperBroker):
    """Simple strategy: Buy on green candle, sell on red candle.
    
    This is the SAME function that would work with live data.
    """
    # Simple strategy logic
    is_green = candle.close > candle.open
    is_red = candle.close < candle.open
    
    if is_green and candle.close > 0:
        # Buy signal
        logger.info(f"🟢 BUY signal at {candle.close}")
        
        # Place order (same interface as kite.place_order())
        result = broker.place_order(
            exchange="NFO",
            tradingsymbol="BANKNIFTY",
            transaction_type="BUY",
            quantity=15,  # 1 lot
            product="MIS",
            order_type="MARKET"
        )
        
        logger.info(f"Order result: {result}")
    
    elif is_red:
        # Sell signal (close position)
        logger.info(f"🔴 SELL signal at {candle.close}")
        
        # Check if we have a position
        positions = broker.positions()
        if positions["net"]:
            result = broker.place_order(
                exchange="NFO",
                tradingsymbol="BANKNIFTY",
                transaction_type="SELL",
                quantity=15,
                product="MIS",
                order_type="MARKET"
            )
            logger.info(f"Order result: {result}")


async def main():
    """Run historical backtest using Zerodha API."""
    logger.info("=" * 80)
    logger.info("ZERODHA HISTORICAL BACKTEST EXAMPLE")
    logger.info("=" * 80)
    
    # Get Kite credentials
    api_key = os.getenv("KITE_API_KEY")
    api_secret = os.getenv("KITE_API_SECRET")
    access_token = os.getenv("KITE_ACCESS_TOKEN")
    
    if not api_key or not access_token:
        logger.error("KITE_API_KEY and KITE_ACCESS_TOKEN required in .env file")
        logger.info("Run: python data_niftybank/src/data_niftybank/tools/kite_auth.py")
        return
    
    # Initialize Kite client
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    # Verify connection
    try:
        profile = kite.profile()
        logger.info(f"Connected to Kite as: {profile.get('user_id')}")
    except Exception as e:
        logger.error(f"Failed to connect to Kite: {e}")
        return
    
    # Create market store
    store = InMemoryMarketStore()
    
    # Create paper broker
    broker = PaperBroker(initial_capital=1000000.0)
    
    # Create callback that has access to broker
    def on_candle_close(candle: OHLCBar):
        """Candle close callback."""
        asyncio.create_task(simple_strategy_on_candle(candle, broker))
    
    # Set date range (last 30 days)
    to_date = date.today()
    from_date = to_date - timedelta(days=30)
    
    # Create unified data flow with Zerodha historical data
    flow = UnifiedDataFlow(
        store=store,
        data_source="zerodha",  # Use Zerodha API
        on_candle_close=on_candle_close,
        paper_broker=broker,
        kite=kite,
        instrument_symbol="NIFTY BANK",  # or "BANKNIFTY" for futures
        from_date=from_date,
        to_date=to_date,
        interval="minute"  # 1-minute candles
    )
    
    # Start data flow
    logger.info(f"Fetching historical data from Zerodha ({from_date} to {to_date})...")
    flow.start()
    
    # Wait for replay to complete
    # The replayer will fetch data and replay it automatically
    logger.info("Running backtest...")
    await asyncio.sleep(30)  # Adjust based on data size
    
    # Stop data flow
    flow.stop()
    
    # Get results
    logger.info("\n" + "=" * 80)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 80)
    
    stats = flow.get_statistics()
    portfolio = broker.get_portfolio_summary()
    
    logger.info(f"Initial Capital: ₹{portfolio['initial_capital']:,.2f}")
    logger.info(f"Final Equity: ₹{portfolio['total_equity']:,.2f}")
    logger.info(f"Total P&L: ₹{portfolio['total_pnl']:,.2f}")
    logger.info(f"Return: {portfolio['return_pct']:.2f}%")
    logger.info(f"Open Positions: {portfolio['open_positions']}")
    logger.info(f"Total Orders: {portfolio['total_orders']}")
    
    # Show positions
    positions = broker.positions()
    if positions["net"]:
        logger.info("\nOpen Positions:")
        for pos in positions["net"]:
            logger.info(
                f"  {pos['tradingsymbol']}: {pos['quantity']} @ ₹{pos['average_price']:.2f} "
                f"(Current: ₹{pos['last_price']:.2f}, P&L: ₹{pos['pnl']:.2f})"
            )
    
    # Show orders
    orders = broker.orders()
    if orders:
        logger.info(f"\nTotal Orders: {len(orders)}")
        for order in orders[-10:]:  # Show last 10
            logger.info(
                f"  {order['transaction_type']} {order['quantity']} {order['tradingsymbol']} "
                f"@ ₹{order.get('average_price', 0):.2f} - {order['status']}"
            )


if __name__ == "__main__":
    asyncio.run(main())


