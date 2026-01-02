"""Unified trading service that integrates data ingestion, trading graph, and position monitoring."""

import asyncio
import logging
import json
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional
from kiteconnect import KiteConnect
from data.ingestion_service import DataIngestionService
from data.market_memory import MarketMemory
from trading_orchestration.trading_graph import TradingGraph
from monitoring.position_monitor import PositionMonitor
from utils.paper_trading import PaperTrading
from config.settings import settings

logger = logging.getLogger(__name__)


class TradingService:
    """Unified trading service that coordinates all components."""
    
    def __init__(self, kite: Optional[KiteConnect] = None, paper_trading: bool = None):
        """Initialize trading service."""
        self.kite = kite
        self.paper_trading = paper_trading if paper_trading is not None else settings.paper_trading_mode
        self.running = False
        
        # Initialize components
        self.market_memory = MarketMemory()
        self.data_ingestion: Optional[DataIngestionService] = None
        self.trading_graph: Optional[TradingGraph] = None
        self.position_monitor: Optional[PositionMonitor] = None
        self.paper_trading_sim: Optional[PaperTrading] = None
        self.news_collector = None
        self.macro_fetcher = None
        
        # Trading loop control
        self.trading_loop_task: Optional[asyncio.Task] = None
        self.position_monitor_task: Optional[asyncio.Task] = None
        
        # Setup signal handlers for graceful shutdown
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"\nReceived signal {signum}, shutting down gracefully...")
        self.shutdown_requested = True
        self.running = False
    
    def _is_market_open(self) -> bool:
        """Check if market is currently open."""
        # 24/7 markets (crypto) are always open
        if settings.market_24_7:
            return True
        
        now = datetime.now()
        current_time = now.time()
        
        try:
            open_time = datetime.strptime(settings.market_open_time, "%H:%M:%S").time()
            close_time = datetime.strptime(settings.market_close_time, "%H:%M:%S").time()
        except ValueError:
            # Fallback if format is different
            open_time = datetime.strptime("09:15:00", "%H:%M:%S").time()
            close_time = datetime.strptime("15:30:00", "%H:%M:%S").time()
        
        # Check if it's a weekday (Monday=0, Sunday=6)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        
        return open_time <= current_time <= close_time
    
    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing trading service...")
        
        try:
            # Initialize paper trading if in paper mode
            if self.paper_trading:
                self.paper_trading_sim = PaperTrading(initial_capital=1000000)
                logger.info("Paper trading simulator initialized")
            
            # Initialize data ingestion based on data source
            if settings.data_source.upper() == "CRYPTO":
                # Crypto data feed doesn't need kite credentials
                logger.info("✅ Crypto data feed will be initialized in start() method")
                logger.info(f"✅ Will use Binance WebSocket for real-time {settings.instrument_name} data")
                self.data_ingestion = None  # Will be created in start() method
            elif self.kite:
                # Use Zerodha WebSocket (DataIngestionService)
                from data.ingestion_service import DataIngestionService
                self.data_ingestion = DataIngestionService(self.kite, self.market_memory)
                logger.info("✅ Zerodha WebSocket data ingestion initialized")
                logger.info(f"✅ Using Zerodha WebSocket for real-time {settings.instrument_name} data")
            else:
                logger.error("=" * 60)
                logger.error("ERROR: No data source configured!")
                logger.error(f"DATA_SOURCE is set to: {settings.data_source}")
                logger.error("For Zerodha: Run 'python auto_login.py' to set up credentials")
                logger.error("For Crypto: Set DATA_SOURCE=CRYPTO in .env")
                logger.error("=" * 60)
                raise ValueError(f"No valid data source configured. DATA_SOURCE={settings.data_source}")
            
            # Initialize trading graph
            self.trading_graph = TradingGraph(kite=self.kite, market_memory=self.market_memory)
            logger.info("Trading graph initialized")
            
            # Initialize position monitor
            self.position_monitor = PositionMonitor(
                kite=self.kite,
                market_memory=self.market_memory,
                paper_trading=self.paper_trading_sim
            )
            logger.info("Position monitor initialized")
            
            # Initialize news collector (if API key configured)
            self.news_collector = None
            if settings.news_api_key:
                from data.news_collector import NewsCollector
                self.news_collector = NewsCollector(self.market_memory)
                logger.info("News collector initialized")
            
            # Initialize macro data fetcher (only for non-crypto instruments)
            self.macro_fetcher = None
            if settings.data_source.upper() != "CRYPTO" and settings.macro_data_enabled:
                try:
                    from data.macro_data_fetcher import MacroDataFetcher
                    self.macro_fetcher = MacroDataFetcher()
                    logger.info("Macro data fetcher initialized")
                except ImportError as e:
                    logger.warning(f"Macro data fetcher not available (missing dependencies): {e}")
                    logger.info("Continuing without macro data fetcher...")
            else:
                logger.info("Macro data fetcher skipped (crypto mode or disabled)")
            
            logger.info("Trading service initialization complete")
            
        except Exception as e:
            logger.error(f"Error initializing trading service: {e}", exc_info=True)
            raise
    
    async def start(self):
        """Start the trading service."""
        if self.running:
            logger.warning("Trading service already running")
            return
        
        await self.initialize()
        
        self.running = True
        logger.info("=" * 60)
        logger.info("Trading Service Starting")
        logger.info("=" * 60)
        logger.info(f"Paper Trading Mode: {self.paper_trading}")
        logger.info(f"Market Open: {self._is_market_open()}")
        logger.info("=" * 60)
        
        try:
            # Start data ingestion - Zerodha or Crypto WebSocket
            if settings.data_source.upper() == "CRYPTO":
                # Use crypto data feed (Binance WebSocket - free)
                from data.crypto_data_feed import CryptoDataFeed
                self.crypto_feed = CryptoDataFeed(self.market_memory)
                self.crypto_feed_task = asyncio.create_task(self.crypto_feed.start())
                logger.info("✅ Crypto data feed (Binance WebSocket) task started")
                logger.info("⏳ Waiting for WebSocket connection to Binance...")
                
                # Wait a moment for connection to establish
                await asyncio.sleep(2)
                
                # Give it a few more seconds to connect and receive first data
                max_wait = 10
                for i in range(max_wait):
                    if self.crypto_feed.connected:
                        logger.info(f"✅ Crypto data feed connected to Binance WebSocket")
                        break
                    await asyncio.sleep(1)
                else:
                    logger.warning("⚠️  Crypto data feed connection still establishing... (may take longer)")
                
                logger.info(f"✅ Crypto data feed initialized - receiving live market data for {settings.instrument_name}...")
            elif self.data_ingestion:
                # Use Zerodha WebSocket
                self.data_ingestion.start()
                logger.info("✅ Zerodha WebSocket data ingestion started")
                logger.info("✅ Receiving live market data from Zerodha...")
            else:
                logger.error("ERROR: Data ingestion service not initialized!")
                raise RuntimeError("Data ingestion service not initialized. Check credentials.")
            
            # Start position monitoring (always running)
            self.position_monitor_task = asyncio.create_task(self.position_monitor.start())
            logger.info("Position monitoring started")
            
            # Start news collector (if configured)
            if self.news_collector:
                asyncio.create_task(self.news_collector.run_continuous())
                logger.info("✅ News collector started - collecting news every 5 minutes")
            
            # Start macro data fetcher (runs daily, only if initialized)
            if self.macro_fetcher:
                asyncio.create_task(self.macro_fetcher.run_continuous(update_interval_hours=24))
                logger.info("✅ Macro data fetcher started - updating daily")
            else:
                logger.info("⏭️  Macro data fetcher skipped (not needed for crypto)")
            
            # Start trading loop (run immediately, then check market status in loop)
            logger.info("=" * 60)
            logger.info("🚀 Starting trading loop (will run analysis immediately, then every 60 seconds)...")
            logger.info("=" * 60)
            self.trading_loop_task = asyncio.create_task(self._trading_loop())
            logger.info("✅ Trading loop task created - waiting for first iteration...")
            # Give it a moment to start
            await asyncio.sleep(1)
            logger.info("✅ Trading loop should be running now - check logs for [LOOP #] messages")
            
            # Keep service running until shutdown requested
            while self.running and not self.shutdown_requested:
                await asyncio.sleep(1)
            
            # Cancel tasks gracefully
            if self.trading_loop_task:
                self.trading_loop_task.cancel()
            if self.position_monitor_task:
                self.position_monitor_task.cancel()
            
            # Wait for tasks to complete cancellation
            if self.trading_loop_task:
                try:
                    await self.trading_loop_task
                except asyncio.CancelledError:
                    pass
            if self.position_monitor_task:
                try:
                    await self.position_monitor_task
                except asyncio.CancelledError:
                    pass
            
        except asyncio.CancelledError:
            logger.info("Trading service cancelled")
        except Exception as e:
            logger.error(f"Error in trading service: {e}", exc_info=True)
            raise
        finally:
            await self.stop()
    
    async def _wait_for_market_open(self):
        """Wait for market to open and then start trading loop."""
        while self.running:
            if self._is_market_open():
                logger.info("Market opened, starting trading loop...")
                self.trading_loop_task = asyncio.create_task(self._trading_loop())
                break
            await asyncio.sleep(60)  # Check every minute
    
    async def _trading_loop(self):
        """Main trading loop that runs every 60 seconds."""
        logger.info("=" * 60)
        logger.info("🚀 Trading Loop Started - This message confirms the loop is running!")
        logger.info("=" * 60)
        
        # Run first analysis immediately
        first_run = True
        
        loop_count = 0
        while self.running and not self.shutdown_requested:
            # Log that we're entering the loop iteration
            logger.info(f"🔄 [LOOP ITERATION] Entering loop iteration #{loop_count + 1}")
            try:
                loop_count += 1
                market_open = self._is_market_open()
                
                if first_run:
                    logger.info(f"🔄 [LOOP #{loop_count}] Running initial trading analysis...")
                    first_run = False
                else:
                    if not market_open:
                        logger.info(f"🔄 [LOOP #{loop_count}] Market is closed - running analysis anyway (for testing/monitoring)")
                    logger.info(f"🔄 [LOOP #{loop_count}] Running trading analysis... (Last analysis was {loop_count * 60} seconds ago)")
                
                # Run trading graph (runs all agents)
                logger.info("=" * 60)
                logger.info("🎯 [TRADING_LOOP] Executing Agent Analysis Pipeline...")
                logger.info("=" * 60)
                
                if not self.trading_graph:
                    logger.error("❌ [TRADING_LOOP] Trading graph not initialized!")
                    raise RuntimeError("Trading graph not initialized")
                
                logger.info("🔄 [TRADING_LOOP] Calling trading_graph.arun()...")
                # Add timeout protection - analysis should complete within 5 minutes
                try:
                    result = await asyncio.wait_for(
                        self.trading_graph.arun(),
                        timeout=300.0  # 5 minutes timeout
                    )
                    logger.info("✅ [TRADING_LOOP] Trading graph execution completed")
                except asyncio.TimeoutError:
                    logger.error("❌ [TRADING_LOOP] Analysis timed out after 5 minutes!")
                    logger.error("This usually means LLM calls are hanging. Check Ollama/LLM provider.")
                    logger.error("Skipping this analysis cycle, will retry in 60 seconds...")
                    await asyncio.sleep(60)
                    continue
                
                # Log decision - handle both dict and AgentState
                if isinstance(result, dict):
                    signal_str = result.get('final_signal', 'HOLD')
                    if hasattr(signal_str, 'value'):
                        signal_str = signal_str.value
                    logger.info("=" * 60)
                    logger.info(f"TRADING DECISION: {signal_str}")
                    logger.info("=" * 60)
                    
                    if signal_str in ["BUY", "SELL"]:
                        logger.info(f"Signal: {signal_str}")
                        logger.info(f"Position Size: {result.get('position_size', 0)}")
                        logger.info(f"Entry Price: {result.get('entry_price', 0)}")
                        logger.info(f"Stop Loss: {result.get('stop_loss', 0)}")
                        logger.info(f"Take Profit: {result.get('take_profit', 0)}")
                else:
                    signal_str = result.final_signal.value if hasattr(result.final_signal, 'value') else str(result.final_signal)
                    logger.info("=" * 60)
                    logger.info(f"TRADING DECISION: {signal_str}")
                    logger.info("=" * 60)
                    
                    if signal_str in ["BUY", "SELL"]:
                        logger.info(f"Signal: {signal_str}")
                        logger.info(f"Position Size: {result.position_size}")
                        logger.info(f"Entry Price: {result.entry_price}")
                        logger.info(f"Stop Loss: {result.stop_loss}")
                        logger.info(f"Take Profit: {result.take_profit}")
                
                logger.info("=" * 60)
                logger.info(f"✅ [LOOP #{loop_count}] Analysis completed successfully")
                logger.info(f"⏳ Next analysis in 60 seconds...")
                logger.info("=" * 60)
                
                # Wait 60 seconds before next analysis (with heartbeat every 10 seconds)
                for i in range(6):
                    await asyncio.sleep(10)
                    if not self.running or self.shutdown_requested:
                        break
                    if i < 5:  # Don't log on last iteration (will log at start of next loop)
                        logger.info(f"⏳ [LOOP #{loop_count}] Waiting... ({60 - (i+1)*10} seconds remaining)")
                
            except asyncio.CancelledError:
                logger.info("🛑 Trading loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ [LOOP #{loop_count}] Error in trading loop: {e}", exc_info=True)
                logger.error(f"❌ [LOOP #{loop_count}] Full error details:", exc_info=True)
                logger.info(f"⏳ [LOOP #{loop_count}] Retrying in 60 seconds...")
                # Wait 60 seconds with heartbeat
                for i in range(6):
                    await asyncio.sleep(10)
                    if not self.running or self.shutdown_requested:
                        break
                    if i < 5:
                        logger.info(f"⏳ [LOOP #{loop_count}] Error recovery wait... ({60 - (i+1)*10} seconds remaining)")
    
    async def stop(self):
        """Stop the trading service gracefully."""
        if not self.running:
            return
        
        logger.info("Stopping trading service...")
        self.running = False
        
        # Stop data ingestion
        if self.data_ingestion:
            self.data_ingestion.stop()
            logger.info("Zerodha WebSocket data ingestion stopped")
        
        # Stop crypto data feed if running
        if hasattr(self, 'crypto_feed') and self.crypto_feed:
            self.crypto_feed.stop()
            if hasattr(self, 'crypto_feed_task') and self.crypto_feed_task:
                self.crypto_feed_task.cancel()
                try:
                    await self.crypto_feed_task
                except asyncio.CancelledError:
                    pass
            logger.info("Crypto data feed stopped")
        
        # Stop position monitoring
        if self.position_monitor:
            self.position_monitor.stop()
            logger.info("Position monitoring stopped")
        
        # Cancel tasks
        if self.trading_loop_task:
            self.trading_loop_task.cancel()
            try:
                await self.trading_loop_task
            except asyncio.CancelledError:
                pass
        
        if self.position_monitor_task:
            self.position_monitor_task.cancel()
            try:
                await self.position_monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Trading service stopped")


def load_kite_credentials() -> dict:
    """Load Kite credentials from credentials.json."""
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        raise FileNotFoundError("credentials.json not found. Run auto_login.py first.")
    
    with open(cred_path) as f:
        return json.load(f)


async def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True  # Override any existing configuration
    )
    
    kite = None
    
    # Check data source - crypto doesn't need Zerodha credentials
    if settings.data_source.upper() == "CRYPTO":
        logger.info("=" * 60)
        logger.info("Crypto Mode Detected")
        logger.info("=" * 60)
        logger.info(f"Instrument: {settings.instrument_name} ({settings.instrument_symbol})")
        logger.info("Data Source: Binance WebSocket (no credentials needed)")
        logger.info("=" * 60)
        # Create trading service without kite (crypto mode)
        service = TradingService(kite=None)
        await service.start()
    else:
        # Zerodha mode - requires credentials
        try:
            # Load Zerodha credentials (required for Zerodha mode)
            creds = load_kite_credentials()
            kite = KiteConnect(api_key=creds["api_key"])
            kite.set_access_token(creds["access_token"])
            logger.info("✅ Zerodha Kite Connect initialized")
            
            # Test connection
            try:
                profile = kite.profile()
                logger.info(f"✅ Connected as: {profile.get('user_name', 'Unknown')}")
            except Exception as e:
                logger.warning(f"Could not fetch profile: {e}")
        except FileNotFoundError:
            logger.error("=" * 60)
            logger.error("ERROR: credentials.json not found!")
            logger.error("Zerodha credentials are required when DATA_SOURCE=ZERODHA")
            logger.error("Please run: python auto_login.py")
            logger.error("=" * 60)
            return
        except Exception as e:
            logger.error(f"ERROR: Could not initialize Zerodha Kite: {e}")
            logger.error("Please check your credentials.json file")
            return
        
        # Create and start trading service with Zerodha
        service = TradingService(kite=kite)
        await service.start()


if __name__ == "__main__":
    asyncio.run(main())

