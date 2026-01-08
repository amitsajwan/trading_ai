"""Example: Historical backtesting with unified data flow.

This demonstrates how to run a strategy on historical data
using the exact same code path as live trading.
"""

import asyncio
import logging
from pathlib import Path

from market_data.src.market_data.store import InMemoryMarketStore
from market_data.src.market_data.adapters.unified_data_flow import UnifiedDataFlow
from market_data.src.market_data.adapters.paper_broker import PaperBroker
from market_data.src.market_data.contracts import OHLCBar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    """Run historical backtest."""
    logger.info("=" * 80)
    logger.info("HISTORICAL BACKTEST EXAMPLE")
    logger.info("=" * 80)
    
    # Create market store
    store = InMemoryMarketStore()
    
    # Create paper broker
    broker = PaperBroker(initial_capital=1000000.0)
    
    # Create callback that has access to broker
    def on_candle_close(candle: OHLCBar):
        """Candle close callback."""
        asyncio.create_task(simple_strategy_on_candle(candle, broker))
    
    # Create unified data flow
    # Option 1: Use synthetic data
    flow = UnifiedDataFlow(
        store=store,
        data_source="synthetic",  # or path to CSV: "data/banknifty_1min.csv"
        on_candle_close=on_candle_close,
        paper_broker=broker
    )
    
    # Start data flow
    flow.start()
    
    # Wait for replay to complete (or run for specified time)
    logger.info("Running backtest...")
    await asyncio.sleep(10)  # Adjust based on data size
    
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
        for order in orders[-5:]:  # Show last 5
            logger.info(
                f"  {order['transaction_type']} {order['quantity']} {order['tradingsymbol']} "
                f"@ ₹{order['average_price']:.2f} - {order['status']}"
            )


if __name__ == "__main__":
    asyncio.run(main())


