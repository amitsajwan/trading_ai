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
        
        # Analysis control
        self.last_analysis_price: Optional[float] = None
        self.last_analysis_time: Optional[datetime] = None
        self.price_change_threshold = 0.005  # 0.5% price change threshold
        self.min_analysis_interval = 300  # Minimum 5 minutes between analyses
        
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
    
    async def _should_run_analysis(self) -> bool:
        """Check if analysis should run based on market conditions."""
        try:
            # Always run analysis if it's the first time
            if self.last_analysis_time is None:
                logger.info("📊 First analysis run - executing")
                return True
            
            # Check minimum time interval
            time_since_last = (datetime.now() - self.last_analysis_time).total_seconds()
            if time_since_last < self.min_analysis_interval:
                logger.info(f"⏰ Too soon since last analysis ({time_since_last:.0f}s < {self.min_analysis_interval}s)")
                return False
            
            # Get current price
            current_price = None
            if self.market_memory:
                instrument_key = settings.instrument_symbol.replace('-', '').replace(' ', '').upper()
                price_data = self.market_memory.get_price_data(instrument_key)
                if price_data:
                    current_price = price_data.get('price')
            
            if current_price is None:
                # If no price data, run analysis to get baseline
                logger.info("💰 No current price data - running analysis")
                return True
            
            # Check for significant price change
            if self.last_analysis_price:
                price_change_pct = abs(current_price - self.last_analysis_price) / self.last_analysis_price
                if price_change_pct >= self.price_change_threshold:
                    logger.info(f"📈 Significant price change: {price_change_pct:.1%} >= {self.price_change_threshold:.1%}")
                    return True
            
            # Check for new news (if news collector exists)
            if hasattr(self, 'news_collector') and self.news_collector:
                try:
                    # Check if there are recent news items since last analysis
                    recent_news = await self.news_collector.get_recent_news(hours=1)
                    if recent_news and len(recent_news) > 0:
                        logger.info(f"📰 New news items detected: {len(recent_news)}")
                        return True
                except Exception as e:
                    logger.debug(f"Error checking news: {e}")
            
            # Check for volume spikes (if futures data available)
            if self.market_memory:
                instrument_key = settings.instrument_symbol.replace('-', '').replace(' ', '').upper()
                futures_data = self.market_memory.get_futures_data(instrument_key)
                if futures_data:
                    volume = futures_data.get('volume', 0)
                    # Simple volume spike detection - could be enhanced
                    if volume > 1000000:  # Arbitrary threshold for BTC volume
                        logger.info(f"📊 High volume detected: {volume:,.0f}")
                        return True
            
            # Force analysis every 15 minutes regardless of conditions
            if time_since_last >= 900:  # 15 minutes
                logger.info("⏰ Force analysis - 15 minutes elapsed")
                return True
            
            logger.info("⏭️ No significant changes - skipping analysis")
            return False
            
        except Exception as e:
            logger.error(f"Error checking analysis conditions: {e}")
            # On error, run analysis to be safe
            return True
    
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
            if settings.finnhub_api_key or settings.eodhd_api_key:
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
                
                # Start crypto feed task with error handling
                async def run_crypto_feed_with_error_handling():
                    """Run crypto feed with proper error handling."""
                    try:
                        await self.crypto_feed.start()
                    except Exception as e:
                        logger.error(f"CRITICAL: Crypto feed task crashed: {e}", exc_info=True)
                        logger.error("Crypto feed will attempt to restart...")
                        # Don't re-raise - let the reconnection loop handle it
                
                self.crypto_feed_task = asyncio.create_task(run_crypto_feed_with_error_handling())
                logger.info("✅ Crypto data feed (Binance WebSocket) task started")
                logger.info("⏳ Waiting for WebSocket connection to Binance...")
                
                # Wait a moment for connection to establish
                await asyncio.sleep(2)
                
                # Give it a few more seconds to connect and receive first data
                max_wait = 15  # Increased wait time
                connected = False
                for i in range(max_wait):
                    # Check if task is still running
                    if self.crypto_feed_task.done():
                        try:
                            await self.crypto_feed_task  # This will raise if there was an error
                        except Exception as e:
                            logger.error(f"Crypto feed task error: {e}")
                            # Task crashed - restart it
                            self.crypto_feed_task = asyncio.create_task(run_crypto_feed_with_error_handling())
                            await asyncio.sleep(2)
                            continue
                    
                    if self.crypto_feed.connected:
                        logger.info(f"✅ Crypto data feed connected to Binance WebSocket")
                        connected = True
                        break
                    await asyncio.sleep(1)
                
                if not connected:
                    logger.warning("⚠️  Crypto data feed connection still establishing...")
                    logger.warning("Check logs for connection errors. Feed will keep trying to connect.")
                
                logger.info(f"✅ Crypto data feed initialized - receiving live market data for {settings.instrument_name}...")
                logger.info("💡 Monitor logs for '[TICK #]' messages to confirm ticks are being received")
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
            interval_minutes = settings.trading_loop_interval_seconds / 60
            logger.info("=" * 60)
            logger.info(f"🚀 Starting trading loop (will run analysis immediately, then every {interval_minutes:.0f} minutes)...")
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
        """Main trading loop that runs every 5 minutes - Agent discussions inform trading decisions."""
        logger.info("=" * 60)
        logger.info("🚀 Trading Loop Started - This message confirms the loop is running!")
        logger.info("=" * 60)
        
        loop_count = 0
        last_cycle_start = None
        
        # Monitor crypto feed task if running
        async def monitor_crypto_feed():
            """Monitor and restart crypto feed if it crashes."""
            if not hasattr(self, 'crypto_feed') or not self.crypto_feed:
                return
            
            while self.running and not self.shutdown_requested:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if hasattr(self, 'crypto_feed_task') and self.crypto_feed_task:
                    if self.crypto_feed_task.done():
                        try:
                            await self.crypto_feed_task  # Check for errors
                        except Exception as e:
                            logger.error(f"CRITICAL: Crypto feed task crashed: {e}", exc_info=True)
                            logger.info("Restarting crypto feed task...")
                            
                            # Restart task - need to reset running flag first
                            self.crypto_feed.running = False
                            self.crypto_feed.connected = False
                            
                            async def run_crypto_feed_with_error_handling():
                                try:
                                    await self.crypto_feed.start()
                                except Exception as e:
                                    logger.error(f"CRITICAL: Crypto feed task crashed again: {e}", exc_info=True)
                            
                            self.crypto_feed_task = asyncio.create_task(run_crypto_feed_with_error_handling())
                            await asyncio.sleep(2)
        
        # Start crypto feed monitor if crypto feed exists
        if hasattr(self, 'crypto_feed') and self.crypto_feed:
            monitor_task = asyncio.create_task(monitor_crypto_feed())
        
        while self.running and not self.shutdown_requested:
            cycle_start_time = asyncio.get_event_loop().time()
            loop_count += 1
            
            # Calculate time since last cycle
            if last_cycle_start:
                actual_gap = cycle_start_time - last_cycle_start
                target_seconds = settings.trading_loop_interval_seconds
                target_minutes = target_seconds / 60
                logger.info(f"🔄 [LOOP #{loop_count}] Starting cycle (gap: {actual_gap:.1f}s, target: {target_seconds}s / {target_minutes:.0f}min)")
            else:
                logger.info(f"🔄 [LOOP #{loop_count}] Starting initial cycle")
            
            last_cycle_start = cycle_start_time
            
            # Check if analysis is needed based on market conditions
            analysis_needed = await self._should_run_analysis()
            
            if not analysis_needed:
                logger.info(f"⏭️ [LOOP #{loop_count}] Skipping analysis - no significant market changes")
                # Still wait for the full interval
                wait_time = float(settings.trading_loop_interval_seconds)
                await asyncio.sleep(wait_time)
                continue
            
            # Run analysis in background task (don't wait for completion)
            analysis_task = None
            try:
                market_open = self._is_market_open()
                
                if not market_open:
                    logger.info(f"🔄 [LOOP #{loop_count}] Market is closed - running analysis anyway (for testing/monitoring)")
                
                logger.info("=" * 60)
                logger.info("🎯 [TRADING_LOOP] Executing Agent Analysis Pipeline...")
                logger.info("=" * 60)
                
                if not self.trading_graph:
                    logger.error("❌ [TRADING_LOOP] Trading graph not initialized!")
                    raise RuntimeError("Trading graph not initialized")
                
                logger.info("🔄 [TRADING_LOOP] Calling trading_graph.arun()...")
                
                # Create analysis task with timeout
                # Timeout slightly longer than loop interval to allow analysis to complete
                timeout_seconds = settings.trading_loop_interval_seconds + 60  # Loop interval + 1 minute buffer
                
                async def run_analysis():
                    try:
                        result = await asyncio.wait_for(
                            self.trading_graph.arun(),
                            timeout=timeout_seconds
                        )
                        
                        # Log decision
                        if isinstance(result, dict):
                            signal_str = result.get('final_signal', 'HOLD')
                            if hasattr(signal_str, 'value'):
                                signal_str = signal_str.value
                        else:
                            signal_str = result.final_signal.value if hasattr(result.final_signal, 'value') else str(result.final_signal)
                        
                        elapsed = asyncio.get_event_loop().time() - cycle_start_time
                        logger.info("=" * 60)
                        logger.info(f"✅ [LOOP #{loop_count}] Analysis completed in {elapsed:.1f}s")
                        logger.info(f"TRADING DECISION: {signal_str}")
                        logger.info("=" * 60)
                        
                        if signal_str in ["BUY", "SELL"]:
                            if isinstance(result, dict):
                                logger.info(f"Signal: {signal_str}")
                                logger.info(f"Position Size: {result.get('position_size', 0)}")
                                logger.info(f"Entry Price: {result.get('entry_price', 0)}")
                            else:
                                logger.info(f"Signal: {signal_str}")
                                logger.info(f"Position Size: {result.position_size}")
                                logger.info(f"Entry Price: {result.entry_price}")
                        
                        # Update analysis tracking
                        self.last_analysis_time = datetime.now()
                        if isinstance(result, dict):
                            self.last_analysis_price = result.get('current_price')
                        else:
                            self.last_analysis_price = result.current_price
                        
                        return result
                    except asyncio.TimeoutError:
                        elapsed = asyncio.get_event_loop().time() - cycle_start_time
                        timeout_minutes = timeout_seconds / 60
                        logger.error(f"❌ [LOOP #{loop_count}] Analysis timed out after {elapsed:.1f}s (timeout: {timeout_seconds}s / {timeout_minutes:.1f}min)!")
                        logger.error("This usually means LLM calls are hanging. Check LLM provider.")
                        return None
                    except Exception as e:
                        elapsed = asyncio.get_event_loop().time() - cycle_start_time
                        logger.error(f"❌ [LOOP #{loop_count}] Analysis error after {elapsed:.1f}s: {e}", exc_info=True)
                        return None
                
                # Start analysis task (don't await - let it run in background)
                analysis_task = asyncio.create_task(run_analysis())
                
            except Exception as e:
                logger.error(f"❌ [LOOP #{loop_count}] Error starting analysis: {e}", exc_info=True)
            
            # Wait for configured interval before next cycle (regardless of analysis completion)
            # This ensures consistent timing - agent discussions inform trading decisions
            wait_start = asyncio.get_event_loop().time()
            wait_time = float(settings.trading_loop_interval_seconds)  # Default: 5 minutes (300s)
            
            # Heartbeat every 30 seconds (for 5-minute cycle)
            heartbeat_interval = 30.0
            while wait_time > 0 and self.running and not self.shutdown_requested:
                sleep_time = min(heartbeat_interval, wait_time)
                await asyncio.sleep(sleep_time)
                wait_time -= sleep_time
                
                if wait_time > 0:
                    wait_minutes = wait_time / 60
                    logger.info(f"⏳ [LOOP #{loop_count}] Next cycle in {wait_time:.0f}s ({wait_minutes:.1f}min)...")
            
            # Check if analysis is still running
            if analysis_task and not analysis_task.done():
                logger.warning(f"⚠️ [LOOP #{loop_count}] Previous analysis still running (took >5min)")
                # Don't cancel - let it finish, but start next cycle anyway
    
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

