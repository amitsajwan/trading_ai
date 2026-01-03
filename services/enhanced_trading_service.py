"""Enhanced Trading Service with Three-Layer Architecture: Strategic, Tactical, Execution."""

import asyncio
import logging
import json
import signal
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from kiteconnect import KiteConnect
from data.market_memory import MarketMemory
from trading_orchestration.trading_graph import TradingGraph
from monitoring.position_monitor import PositionMonitor
from services.strategy_manager import StrategyManager
from agents.review_agent import ReviewAgent
from engines.rule_engine import RuleEngine
from engines.strategy_planner import StrategyPlanner
from engines.instrument_detector import InstrumentDetector
from utils.paper_trading import PaperTrading
from config.settings import settings

logger = logging.getLogger(__name__)


class EnhancedTradingService:
    """Enhanced trading service with three-layer architecture."""
    
    def __init__(self, kite: Optional[KiteConnect] = None, paper_trading: bool = None):
        """Initialize enhanced trading service."""
        self.kite = kite
        self.paper_trading = paper_trading if paper_trading is not None else settings.paper_trading_mode
        self.running = False
        
        # Core components
        self.market_memory = MarketMemory()
        self.strategy_manager = StrategyManager()
        self.review_agent = ReviewAgent()
        self.rule_engine: Optional[RuleEngine] = None
        self.strategy_planner: Optional[StrategyPlanner] = None
        self.trading_graph: Optional[TradingGraph] = None
        self.position_monitor: Optional[PositionMonitor] = None
        
        # Instrument detection
        self.instrument_detector = InstrumentDetector()
        self.instrument_profile = None
        
        # Layer tasks
        self.strategic_layer_task: Optional[asyncio.Task] = None
        self.tactical_layer_task: Optional[asyncio.Task] = None
        self.execution_layer_task: Optional[asyncio.Task] = None
        
        # Configuration - Optimized timing based on analysis
        # Strategic: 15 min (balanced - agents have time for reasoning, more responsive than 20)
        # Tactical: 3 min (more responsive than 5, catches changes faster)
        # Will be adjusted based on instrument profile
        self.strategic_interval_minutes = 15  # Default, will be adjusted
        self.tactical_interval_minutes = 3    # Quick validation every 3 min
        
        # Track recent trades for review
        self.recent_trades: List[Dict[str, Any]] = []
        
        # Setup signal handlers
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"\nReceived signal {signum}, shutting down gracefully...")
        self.shutdown_requested = True
        self.running = False
    
    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Enhanced Trading Service...")
        
        try:
            # Initialize strategy manager
            await self.strategy_manager.initialize()
            logger.info("✅ Strategy Manager initialized")
            
            # Detect instrument (generic)
            self.instrument_profile = self.instrument_detector.detect(
                symbol=settings.instrument_symbol,
                exchange=settings.instrument_exchange,
                data_source=settings.data_source
            )
            
            # Adjust analysis frequency based on instrument
            self.strategic_interval_minutes = self.instrument_profile.optimal_frequency_minutes
            
            logger.info(
                f"✅ Detected instrument: {self.instrument_profile.instrument_type} "
                f"({self.instrument_profile.currency}, {self.instrument_profile.region})"
            )
            logger.info(
                f"✅ Analysis frequency: {self.strategic_interval_minutes} min "
                f"(optimal for {self.instrument_profile.instrument_type})"
            )
            
            # Initialize strategy planner (generic - works for any instrument)
            self.strategy_planner = StrategyPlanner(kite=self.kite, market_memory=self.market_memory)
            await self.strategy_planner.initialize()
            logger.info("✅ Strategy Planner initialized (generic)")
            
            # Initialize rule engine
            self.rule_engine = RuleEngine(kite=self.kite, market_memory=self.market_memory)
            await self.rule_engine.initialize()
            logger.info("✅ Rule Engine initialized")
            
            # Initialize trading graph
            self.trading_graph = TradingGraph(kite=self.kite, market_memory=self.market_memory)
            logger.info("✅ Trading Graph initialized")
            
            # Initialize position monitor
            paper_trading_sim = PaperTrading() if self.paper_trading else None
            self.position_monitor = PositionMonitor(
                kite=self.kite,
                market_memory=self.market_memory,
                paper_trading=paper_trading_sim
            )
            logger.info("✅ Position Monitor initialized")
            
        except Exception as e:
            logger.error(f"Error initializing enhanced trading service: {e}", exc_info=True)
            raise
    
    async def start(self):
        """Start the enhanced trading service with three-layer architecture."""
        if self.running:
            logger.warning("Enhanced trading service already running")
            return
        
        await self.initialize()
        self.running = True
        
        logger.info("=" * 70)
        logger.info("🚀 Enhanced Trading Service Starting")
        logger.info("=" * 70)
        logger.info("Architecture: Three-Layer GenAI-Enhanced System")
        logger.info(f"  Layer 1 (Strategic): Every {self.strategic_interval_minutes} min")
        logger.info("     → Deep multi-agent analysis with proper reasoning (2-4 min)")
        logger.info("     → Agents debate and create comprehensive strategy")
        logger.info(f"  Layer 2 (Tactical): Every {self.tactical_interval_minutes} min")
        logger.info("     → Quick market validation (<30s)")
        logger.info("     → Strategy still valid check")
        logger.info("  Layer 3 (Execution): Continuous")
        logger.info("     → Rule-based execution (<50ms per tick)")
        logger.info("     → Instant trade execution when conditions met")
        logger.info("")
        logger.info("💡 Timing Analysis:")
        logger.info(f"   • Strategic: {self.strategic_interval_minutes} min (optimal balance)")
        logger.info(f"     - More responsive than 20 min ({25 if self.strategic_interval_minutes == 15 else 18} analyses/day)")
        logger.info(f"     - Agents have time for proper reasoning (3-6 min + buffer)")
        logger.info(f"   • Tactical: {self.tactical_interval_minutes} min (more responsive)")
        logger.info(f"     - Better than 5 min ({125 if self.tactical_interval_minutes == 3 else 75} validations/day)")
        logger.info("     - Catches market changes faster")
        logger.info("=" * 70)
        
        try:
            # Start all three layers concurrently
            self.strategic_layer_task = asyncio.create_task(self._strategic_layer_loop())
            self.tactical_layer_task = asyncio.create_task(self._tactical_layer_loop())
            self.execution_layer_task = asyncio.create_task(self._execution_layer_loop())
            
            # Start position monitoring
            if self.position_monitor:
                position_monitor_task = asyncio.create_task(self.position_monitor.start())
            
            # Run until shutdown
            await asyncio.gather(
                self.strategic_layer_task,
                self.tactical_layer_task,
                self.execution_layer_task
            )
            
        except asyncio.CancelledError:
            logger.info("Enhanced trading service cancelled")
        except Exception as e:
            logger.error(f"Error in enhanced trading service: {e}", exc_info=True)
        finally:
            await self.stop()
    
    async def _strategic_layer_loop(self):
        """Layer 1: Strategic Intelligence - Deep multi-agent analysis every 15-30 min."""
        logger.info("=" * 70)
        logger.info("🎯 Strategic Layer Started")
        logger.info(f"   Deep analysis every {self.strategic_interval_minutes} minutes")
        logger.info("=" * 70)
        
        # Run immediately on start
        await self._create_strategic_strategy()
        
        while self.running and not self.shutdown_requested:
            try:
                await asyncio.sleep(self.strategic_interval_minutes * 60)
                if self.running:
                    await self._create_strategic_strategy()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in strategic layer: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 min before retry
    
    async def _create_strategic_strategy(self):
        """Create comprehensive strategy through deep analysis - generic for any instrument."""
        try:
            logger.info("=" * 70)
            logger.info("🧠 STRATEGIC LAYER: Creating comprehensive strategy...")
            logger.info(f"   Instrument: {settings.instrument_symbol} ({self.instrument_profile.instrument_type if self.instrument_profile else 'UNKNOWN'})")
            logger.info("=" * 70)
            
            # Generate trading rules using StrategyPlanner (generic)
            if self.strategy_planner:
                logger.info("📊 Generating trading rules using StrategyPlanner...")
                rules = await self.strategy_planner.generate_rules()
                
                if rules:
                    logger.info(f"✅ Generated {len(rules.get('rules', []))} trading rules")
                    logger.info(f"   Strategy ID: {rules.get('strategy_id', 'N/A')}")
                    logger.info(f"   Valid until: {rules.get('valid_until', 'N/A')}")
                    
                    # Rules are already stored in Redis by StrategyPlanner
                    # Reload in rule engine
                    await self.rule_engine.load_rules()
                    logger.info("✅ Rules loaded into Rule Engine")
                else:
                    logger.warning("⚠️  No rules generated by StrategyPlanner")
            
            # Also run full agent analysis pipeline (if trading graph available)
            # This provides additional context and can be used alongside rules
            if self.trading_graph:
                logger.info("🔄 Running multi-agent analysis pipeline (additional context)...")
                try:
                    result = await asyncio.wait_for(
                        self.trading_graph.arun(),
                        timeout=300.0  # 5 minutes for deep analysis
                    )
                    
                    # Extract adaptive strategy from result
                    if isinstance(result, dict):
                        adaptive_strategy = result.get("adaptive_strategy")
                        signal = result.get("final_signal")
                    else:
                        adaptive_strategy = result.adaptive_strategy if hasattr(result, 'adaptive_strategy') else None
                        signal = result.final_signal if hasattr(result, 'final_signal') else None
                    
                    if adaptive_strategy:
                        # Store as additional strategy context
                        strategy = await self.strategy_manager.create_strategy(
                            adaptive_strategy,
                            valid_duration_minutes=self.strategic_interval_minutes + 5
                        )
                        logger.info(f"✅ Additional strategy context stored: {strategy.get('strategy_id')}")
                except asyncio.TimeoutError:
                    logger.warning("⚠️  Trading graph analysis timed out (non-critical)")
                except Exception as e:
                    logger.warning(f"⚠️  Trading graph analysis failed: {e} (non-critical)")
            
            logger.info("=" * 70)
            logger.info("✅ STRATEGIC ANALYSIS COMPLETE")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"Error creating strategic strategy: {e}", exc_info=True)
    
    async def _review_previous_strategy(self, strategy: Dict[str, Any]):
        """Review previous strategy performance."""
        try:
            logger.info("📊 Reviewing previous strategy performance...")
            
            # Get recent trades for this strategy
            strategy_id = strategy.get("strategy_id")
            recent_trades = [
                t for t in self.recent_trades
                if t.get("strategy_id") == strategy_id
            ]
            
            # Create minimal state for review agent
            from agents.state import AgentState
            review_state = AgentState()
            
            # Run review agent
            review_output = self.review_agent.process(
                state=review_state,
                recent_trades=recent_trades,
                previous_strategy=strategy
            )
            
            logger.info(f"📈 Review Results:")
            logger.info(f"   Trades analyzed: {len(recent_trades)}")
            logger.info(f"   Win rate: {review_output.get('trade_analysis', {}).get('win_rate', 0):.2%}")
            logger.info(f"   Strategy effectiveness: {review_output.get('strategy_analysis', {}).get('strategy_effectiveness', 0):.2f}")
            
            # Log learnings
            learnings = review_output.get("learnings", [])
            if learnings:
                logger.info("💡 Key Learnings:")
                for learning in learnings[:3]:  # Top 3
                    logger.info(f"   - {learning}")
            
        except Exception as e:
            logger.error(f"Error reviewing previous strategy: {e}")
    
    def _create_default_strategy(self, result) -> Dict[str, Any]:
        """Create default strategy if agents didn't create one."""
        from datetime import datetime
        
        if isinstance(result, dict):
            signal = result.get("final_signal", "HOLD")
            position_size = result.get("position_size", 0)
        else:
            signal = result.final_signal.value if hasattr(result.final_signal, 'value') else "HOLD"
            position_size = result.position_size if hasattr(result, 'position_size') else 0
        
        return {
            "strategy_id": f"default_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "type": "ADAPTIVE",
            "signal": signal,
            "position_size": position_size,
            "entry_conditions": [],
            "exit_conditions": {},
            "agent_reasoning": {}
        }
    
    async def _tactical_layer_loop(self):
        """Layer 2: Tactical Updates - Quick validation every 5 min."""
        logger.info("=" * 70)
        logger.info("⚡ Tactical Layer Started")
        logger.info(f"   Quick validation every {self.tactical_interval_minutes} minutes")
        logger.info("=" * 70)
        
        # Wait a bit before first check (let strategic layer create initial strategy)
        await asyncio.sleep(60)  # 1 minute
        
        while self.running and not self.shutdown_requested:
            try:
                await self._tactical_validation()
                await asyncio.sleep(self.tactical_interval_minutes * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in tactical layer: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _tactical_validation(self):
        """
        Quick validation and monitoring - runs every 3 minutes regardless of signal.
        Even with HOLD, we monitor for changes that could trigger a new strategy.
        """
        try:
            current_strategy = await self.strategy_manager.get_current_strategy()
            if not current_strategy:
                logger.debug("No current strategy to validate")
                return
            
            # Quick market check
            instrument = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
            current_price = self.market_memory.get_current_price(instrument)
            
            if not current_price:
                return
            
            signal = current_strategy.get("signal", "HOLD")
            strategy_id = current_strategy.get("strategy_id", "unknown")
            
            # Check if strategy is still valid
            is_valid = await self.strategy_manager.is_strategy_valid()
            
            if not is_valid:
                logger.warning(f"⚠️ Strategy {strategy_id} has expired - strategic layer will create new one")
                return
            
            # Get strategy creation time and price
            strategy_created_at = current_strategy.get("created_at")
            strategy_entry_price = current_strategy.get("agent_reasoning", {}).get("entry_price") or current_price
            
            # Calculate price change since strategy creation
            price_change_pct = abs((current_price - strategy_entry_price) / strategy_entry_price * 100)
            
            # Get volatility change (if available)
            current_ohlc = self.market_memory.get_ohlc_data(instrument, "1min", limit=20)
            volatility_change = None
            if current_ohlc and len(current_ohlc) >= 10:
                recent_prices = [c.get("close", current_price) for c in current_ohlc[-10:]]
                if len(recent_prices) > 1:
                    volatility = np.std(recent_prices) / np.mean(recent_prices) * 100
                    volatility_change = volatility
            
            # Monitor conditions regardless of signal type
            logger.info(f"📊 Tactical Validation [{signal}]: Price={current_price:.2f}, Change={price_change_pct:.2f}%")
            
            # Check for significant changes that might warrant early strategic update
            significant_change = False
            change_reason = []
            
            # Price move threshold (adaptive based on signal)
            if signal == "HOLD":
                price_threshold = 1.5  # 1.5% move for HOLD (more sensitive)
            else:
                price_threshold = 2.5  # 2.5% move for BUY/SELL
            
            if price_change_pct > price_threshold:
                significant_change = True
                change_reason.append(f"Price moved {price_change_pct:.2f}%")
            
            # Volatility spike
            if volatility_change and volatility_change > 3.0:  # 3% volatility
                significant_change = True
                change_reason.append(f"Volatility spike: {volatility_change:.2f}%")
            
            # If significant change detected, log it (strategic layer will handle on next cycle)
            if significant_change:
                logger.warning(f"⚠️ Significant market change detected: {', '.join(change_reason)}")
                logger.info(f"   Current strategy [{signal}] may need update on next strategic cycle")
                # Note: We don't trigger early update here to avoid over-trading
                # Strategic layer (15 min) will pick this up
            
            # For HOLD signals, also check if conditions are becoming favorable
            if signal == "HOLD":
                # Check if we're getting closer to entry conditions
                entry_conditions = current_strategy.get("entry_conditions", [])
                if entry_conditions:
                    logger.debug(f"   Monitoring {len(entry_conditions)} entry conditions...")
                    # Rule engine will evaluate these continuously
            
            logger.debug(f"✅ Tactical validation complete: Strategy [{signal}] still valid, monitoring continues")
            
        except Exception as e:
            logger.error(f"Error in tactical validation: {e}", exc_info=True)
    
    async def _execution_layer_loop(self):
        """Layer 3: Real-Time Execution - Continuous rule-based execution."""
        logger.info("=" * 70)
        logger.info("⚙️  Execution Layer Started")
        logger.info("   Continuous rule-based execution (<50ms per tick)")
        logger.info("=" * 70)
        
        while self.running and not self.shutdown_requested:
            try:
                # Get latest tick
                tick = await self._get_latest_tick()
                
                if tick:
                    # Get current strategy
                    strategy = await self.strategy_manager.get_current_strategy()
                    
                    if strategy:
                        # Convert strategy to rule format for rule engine
                        rules = self._strategy_to_rules(strategy)
                        
                        # Store rules temporarily for rule engine
                        if self.rule_engine and self.rule_engine.redis_client:
                            rules_json = json.dumps({"rules": rules})
                            await self.rule_engine.redis_client.setex(
                                "active_rules",
                                300,  # 5 min TTL
                                rules_json
                            )
                        
                        # Evaluate rules
                        signals = await self.rule_engine.evaluate_rules(tick)
                        
                        # Execute trades
                        for signal in signals:
                            order_result = await self.rule_engine.execute_trade(signal, tick)
                            if order_result:
                                # Track trade for review
                                self.recent_trades.append({
                                    "strategy_id": strategy.get("strategy_id"),
                                    "timestamp": datetime.now().isoformat(),
                                    "entry_price": signal.get("entry_price"),
                                    "direction": signal.get("direction"),
                                    "order_id": order_result.get("order_id")
                                })
                                # Keep only last 50 trades
                                self.recent_trades = self.recent_trades[-50:]
                
                # Small delay to avoid CPU spinning
                await asyncio.sleep(0.1)  # 10Hz
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in execution layer: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    def _strategy_to_rules(self, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert adaptive strategy to rule engine format."""
        entry_conditions = strategy.get("entry_conditions", [])
        signal = strategy.get("signal", "HOLD")
        
        if signal == "HOLD" or not entry_conditions:
            return []
        
        rule = {
            "rule_id": f"rule_{strategy.get('strategy_id')}",
            "name": f"Strategy {strategy.get('strategy_id')}",
            "direction": signal,
            "instrument": settings.instrument_symbol,
            "conditions": self._convert_conditions(entry_conditions),
            "position_size": {"risk_pct": strategy.get("position_sizing", {}).get("risk_pct", 2.0)},
            "stop_loss": {"premium_pct": -abs(strategy.get("exit_conditions", {}).get("stop_loss", 0))},
            "target": {"premium_pct": abs(strategy.get("exit_conditions", {}).get("take_profit", [0])[0] if isinstance(strategy.get("exit_conditions", {}).get("take_profit"), list) else 0)},
            "max_trades": strategy.get("position_sizing", {}).get("max_positions", 2)
        }
        
        return [rule]
    
    def _convert_conditions(self, conditions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert strategy conditions to rule engine format."""
        rule_conditions = []
        
        for cond in conditions:
            cond_type = cond.get("type")
            
            if cond_type == "price_above":
                rule_conditions.append({
                    "type": "fut_ltp_above",
                    "value": cond.get("value")
                })
            elif cond_type == "price_below":
                rule_conditions.append({
                    "type": "fut_ltp_below",
                    "value": cond.get("value")
                })
            elif cond_type == "rsi_between":
                rule_conditions.append({
                    "type": "rsi_5_above",
                    "value": cond.get("min", 40)
                })
                # Note: Would need rsi_below condition type in rule engine
        
        return rule_conditions
    
    async def _get_latest_tick(self) -> Optional[Dict[str, Any]]:
        """Get latest tick from market memory."""
        try:
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
        """Stop the enhanced trading service."""
        if not self.running:
            return
        
        logger.info("Stopping enhanced trading service...")
        self.running = False
        
        # Cancel tasks
        for task in [self.strategic_layer_task, self.tactical_layer_task, self.execution_layer_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info("Enhanced trading service stopped")

