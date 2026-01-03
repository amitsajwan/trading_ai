"""Rule-based execution service that runs rule engine on every tick."""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from kiteconnect import KiteConnect
from engines.rule_engine import RuleEngine
from engines.strategy_planner import StrategyPlanner
from data.options_chain_fetcher import OptionsChainFetcher
from data.market_memory import MarketMemory
from config.settings import settings

logger = logging.getLogger(__name__)


class RuleExecutionService:
    """Service that runs rule engine on every tick and strategy planner every 5 minutes."""
    
    def __init__(self, kite: Optional[KiteConnect] = None, market_memory: Optional[MarketMemory] = None):
        """Initialize rule execution service."""
        self.kite = kite
        self.market_memory = market_memory or MarketMemory()
        self.rule_engine: Optional[RuleEngine] = None
        self.strategy_planner: Optional[StrategyPlanner] = None
        self.options_chain_fetcher: Optional[OptionsChainFetcher] = None
        self.running = False
        self.last_chain_snapshot = None
        
    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing rule execution service...")
        
        try:
            # Initialize rule engine
            self.rule_engine = RuleEngine(kite=self.kite, market_memory=self.market_memory)
            await self.rule_engine.initialize()
            await self.rule_engine.load_rules()
            logger.info("✅ Rule engine initialized")
            
            # Initialize strategy planner
            self.strategy_planner = StrategyPlanner(kite=self.kite, market_memory=self.market_memory)
            await self.strategy_planner.initialize()
            logger.info("✅ Strategy planner initialized")
            
            # Initialize options chain fetcher
            if self.kite:
                self.options_chain_fetcher = OptionsChainFetcher(self.kite, self.market_memory)
                await self.options_chain_fetcher.initialize()
                logger.info("✅ Options chain fetcher initialized")
            
        except Exception as e:
            logger.error(f"Error initializing rule execution service: {e}", exc_info=True)
            raise
    
    async def start(self):
        """Start the rule execution service."""
        if self.running:
            logger.warning("Rule execution service already running")
            return
        
        await self.initialize()
        self.running = True
        
        logger.info("=" * 60)
        logger.info("🚀 Rule Execution Service Starting")
        logger.info("=" * 60)
        logger.info("Mode: Rule-based execution (<50ms per tick)")
        logger.info("Strategy Planner: Runs every 5 minutes")
        logger.info("Rule Engine: Runs on every tick")
        logger.info("=" * 60)
        
        # Start strategy planner task (runs every 5 minutes)
        planner_task = asyncio.create_task(self._strategy_planner_loop())
        
        # Start rule engine task (runs on tick events)
        engine_task = asyncio.create_task(self._rule_engine_loop())
        
        try:
            # Run both tasks concurrently
            await asyncio.gather(planner_task, engine_task)
        except asyncio.CancelledError:
            logger.info("Rule execution service cancelled")
        except Exception as e:
            logger.error(f"Error in rule execution service: {e}", exc_info=True)
        finally:
            await self.stop()
    
    async def _strategy_planner_loop(self):
        """Run strategy planner every 5 minutes."""
        logger.info("Strategy planner loop started (runs every 5 minutes)")
        
        # Run immediately on start
        await self._generate_strategies()
        
        while self.running:
            try:
                await asyncio.sleep(300)  # 5 minutes
                if self.running:
                    await self._generate_strategies()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in strategy planner loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def _generate_strategies(self):
        """Generate new trading strategies."""
        try:
            logger.info("=" * 60)
            logger.info("🎯 Generating new trading strategies...")
            logger.info("=" * 60)
            
            rules = await self.strategy_planner.generate_rules()
            
            if rules:
                logger.info(f"✅ Generated {len(rules.get('rules', []))} new rules")
                # Reload rules in engine
                await self.rule_engine.load_rules()
            else:
                logger.warning("No rules generated")
                
        except Exception as e:
            logger.error(f"Error generating strategies: {e}", exc_info=True)
    
    async def _rule_engine_loop(self):
        """Run rule engine on tick events."""
        logger.info("Rule engine loop started (listening for ticks)")
        
        # Subscribe to tick updates from market memory
        # In a real implementation, this would subscribe to WebSocket ticks
        # For now, we'll poll Redis for latest ticks
        
        while self.running:
            try:
                # Get latest tick from Redis
                tick = await self._get_latest_tick()
                
                if tick:
                    # Fetch options chain data if available
                    if self.options_chain_fetcher:
                        chain_data = await self.options_chain_fetcher.fetch_options_chain()
                        if chain_data:
                            # Calculate OI changes
                            oi_changes = await self.options_chain_fetcher.get_oi_changes(
                                chain_data,
                                self.last_chain_snapshot
                            )
                            tick["oi_data"] = oi_changes
                            self.last_chain_snapshot = chain_data
                    
                    # Evaluate rules
                    signals = await self.rule_engine.evaluate_rules(tick)
                    
                    # Execute trades for matching signals
                    for signal in signals:
                        await self.rule_engine.execute_trade(signal, tick)
                
                # Small delay to avoid CPU spinning
                await asyncio.sleep(0.1)  # 10Hz polling
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rule engine loop: {e}", exc_info=True)
                await asyncio.sleep(1)  # Wait 1 second before retry
    
    async def _get_latest_tick(self) -> Optional[dict]:
        """Get latest tick from Redis."""
        try:
            if not self.rule_engine or not self.rule_engine.redis_client:
                return None
            
            # Get latest price from market memory
            instrument = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
            price = self.market_memory.get_current_price(instrument)
            
            if price:
                return {
                    "instrument": instrument,
                    "ltp": price,
                    "last_price": price,
                    "price": price,
                    "timestamp": datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting latest tick: {e}")
            return None
    
    async def stop(self):
        """Stop the rule execution service."""
        if not self.running:
            return
        
        logger.info("Stopping rule execution service...")
        self.running = False
        
        logger.info("Rule execution service stopped")

