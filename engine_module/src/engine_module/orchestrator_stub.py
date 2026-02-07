"""Orchestrator stub implementation for trading engine.

This module provides a skeleton TradingOrchestrator that demonstrates
dependency injection and async execution flow. Implementation details
are left as TODOs for incremental development.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from datetime import datetime, timedelta

from .contracts import AnalysisResult, TechnicalDataProvider, PositionManagerProvider

# Import time service for virtual/historical time support
try:
    from core_kernel.src.core_kernel.time_service import now as get_system_time
except ImportError:
    # Fallback if time service not available
    def get_system_time() -> datetime:
        return datetime.now()

logger = logging.getLogger(__name__)


# Import contracts from other modules via duck typing
# (avoid hard dependencies on other modules in implementation)
@runtime_checkable
class LLMClient(Protocol):
    """LLM client protocol for type hints."""
    async def generate(self, request: Any) -> Any:
        ...


@runtime_checkable
class MarketStore(Protocol):
    """Market store protocol for type hints."""
    async def get_latest_ticks(self, instrument: str, limit: int) -> list[Any]:
        ...

    async def get_ohlc(self, instrument: str, start: Any, end: Any) -> list[Any]:
        ...


@runtime_checkable
class OptionsData(Protocol):
    """Options data protocol for type hints."""
    async def fetch_chain(self, instrument: str, expiry: Any) -> Dict[str, Any]:
        ...


@runtime_checkable
class NewsService(Protocol):
    """News service protocol for type hints."""
    async def get_latest_news(self, instrument: str, limit: int = 10) -> list[Any]:
        ...

    async def get_sentiment_summary(self, instrument: str, hours: int = 24) -> Dict[str, Any]:
        ...


@runtime_checkable
class PositionManager(Protocol):
    """Position manager protocol for type hints."""
    async def get_positions(self, symbol: str | None = None) -> list[Any]:
        ...

    async def execute_trading_decision(self, decision: Dict[str, Any]) -> Any:
        ...

    def get_portfolio_summary(self) -> Dict[str, Any]:
        ...


@runtime_checkable
class Agent(Protocol):
    """Agent protocol for type hints."""
    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        ...


class TradingOrchestrator:
    """Orchestrator stub demonstrating dependency injection pattern.
    
    Coordinates market data fetch, agent analysis, and decision making.
    Agents are not yet wired, but the structure shows how they will be injected.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        market_data_provider=None,  # Changed from market_store
        options_data_provider=None,  # Changed from options_data
        agents: Optional[list[Agent]] = None,
        news_service: Optional[NewsService] = None,
        technical_data_provider: Optional[TechnicalDataProvider] = None,
        macro_data_provider=None,  # Provider for macroeconomic data
        position_manager: Optional[PositionManager] = None,
        signal_monitor=None,  # SignalMonitor instance for real-time signal monitoring
        mongo_db=None,  # MongoDB database instance for signal persistence
        max_concurrent_agents: int = 5,  # Rate limiting for agent execution
        **kwargs: Any,
    ) -> None:
        """Initialize orchestrator with injected dependencies.
        
        Args:
            llm_client: GenAI client for LLM requests
            market_data_provider: Provider for market data (OHLC, ticks)
            options_data_provider: Provider for options chain data
            agents: List of analysis agents (technical, sentiment, etc.)
            news_service: News service for sentiment analysis (optional)
            technical_data_provider: Provider for technical indicators (optional)
            position_manager: Position manager for live position tracking (optional)
            signal_monitor: SignalMonitor instance for conditional signal monitoring (optional)
            mongo_db: MongoDB database instance for signal persistence (optional)
            **kwargs: Additional config (e.g., instruments, lookback_days)
        """
        self.llm_client = llm_client
        self.market_data_provider = market_data_provider
        self.options_data_provider = options_data_provider
        self.agents = agents or []
        self.news_service = news_service
        self.technical_data_provider = technical_data_provider
        self.macro_data_provider = macro_data_provider
        self.position_manager = position_manager
        self.signal_monitor = signal_monitor
        self.mongo_db = mongo_db
        self.config = kwargs

        # Rate limiting semaphore for concurrent agent execution
        import asyncio
        self._agent_semaphore = asyncio.Semaphore(max_concurrent_agents)
        logger.info(f"TradingOrchestrator: initialized with max_concurrent_agents={max_concurrent_agents}")

        # Optional: auto-execute signals when they trigger (kept loosely coupled via callback)
        # This wires conditional signal triggers -> PositionManager execution.
        try:
            auto_exec = bool(self.config.get("auto_execute_signals", False))
            if auto_exec and self.signal_monitor and self.position_manager and hasattr(self.signal_monitor, "set_execution_callback"):
                self.signal_monitor.set_execution_callback(self._on_signal_triggered)
                logger.info("TradingOrchestrator: auto_execute_signals enabled (callback registered)")
        except Exception as e:
            logger.debug(f"TradingOrchestrator: failed to register signal execution callback: {e}")

    async def run_cycle(self, context: Dict[str, Any]) -> AnalysisResult:
        """Execute one trading cycle: fetch data, analyze, decide on options strategies.

        This orchestrator runs every 15 minutes during market hours and provides
        options trading strategies based on comprehensive market analysis.

        Args:
            context: Execution context with:
                - instrument: "BANKNIFTY" or "NIFTY"
                - timestamp: Current timestamp
                - market_hours: Boolean indicating if market is open
                - cycle_interval: "15min" for analysis cadence

        Returns:
            AnalysisResult with options trading decision and analysis
        """
        print("🚀 ORCHESTRATOR: run_cycle() called!")
        instrument = context.get("instrument", "BANKNIFTY")  # Default to BANKNIFTY Futures (nearest expiry)
        # Use virtual time if available, otherwise use provided timestamp or current time
        timestamp = context.get("timestamp", get_system_time())
        
        # Handle timestamp as string or datetime object
        if isinstance(timestamp, str):
            from dateutil import parser
            timestamp = parser.isoparse(timestamp)
        elif not isinstance(timestamp, datetime):
            timestamp = get_system_time()
        
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            from datetime import timezone
            timestamp = timestamp.replace(tzinfo=timezone.utc)
            
        market_hours = context.get("market_hours", False)
        execution_mode = context.get("execution_mode", "LIVE")

        # In BACKTEST mode, always consider market open for signal generation
        if execution_mode == "BACKTEST":
            market_hours = True
            logger.info(f"BACKTEST mode: Forcing market hours to OPEN for signal generation")

        cycle_interval = context.get("cycle_interval", "15min")

        logger.info(f"Starting {cycle_interval} analysis cycle for {instrument} at {timestamp} (market: {'OPEN' if market_hours else 'CLOSED'})")

        # Initialize cycle counter if not exists
        if not hasattr(self, '_cycle_count'):
            self._cycle_count = 0
        self._cycle_count += 1

        # Add cycle info to context for publishing
        context['cycle_info'] = {
            'cycle_number': self._cycle_count,
            'cycle_interval': cycle_interval,
            'start_time': timestamp.isoformat()
        }

        try:
            # Step 0: Invalidate previous signals for this instrument (15-min cadence)
            # - Remove from Mongo pending set
            # - Remove from in-memory SignalMonitor (if present)
            try:
                if self.mongo_db is not None:
                    from .signal_creator import cancel_pending_signals
                    await cancel_pending_signals(self.mongo_db, instrument=instrument, reason="cycle_invalidation")
            except Exception as e:
                logger.debug(f"Signal invalidation (Mongo) skipped/failed: {e}")

            try:
                if self.signal_monitor and hasattr(self.signal_monitor, "remove_signals_for_instrument"):
                    self.signal_monitor.remove_signals_for_instrument(instrument)
            except Exception as e:
                logger.debug(f"Signal invalidation (monitor) skipped/failed: {e}")

            # Step 1: Fetch market data (15min OHLC + recent ticks)
            market_data = await self._fetch_market_data(instrument)

            # Step 2: Fetch options chain data
            options_chain = await self._fetch_options_data(instrument)

            # Step 3: Fetch news data (if news service available)
            news_data = await self._fetch_news_data(instrument)

            # Step 3.5: Fetch technical indicators (if technical data provider available)
            technical_data = await self._fetch_technical_data(instrument)

            # Step 3.6: Fetch macro data (if macro data provider available)
            macro_data = await self._fetch_macro_data(instrument)

            # Step 3.7: Fetch position data (if position manager available)
            position_data = await self._fetch_position_data(instrument)

            # Step 4: Run all agents in parallel
            agent_execution_result = await self._run_agents_parallel(market_data, options_chain, news_data, technical_data, macro_data, position_data, context)

            # Safety check: ensure we got a proper tuple return
            if isinstance(agent_execution_result, tuple) and len(agent_execution_result) == 2:
                agent_results, failed_agents = agent_execution_result
            else:
                logger.error(f"❌ CRITICAL: _run_agents_parallel returned {type(agent_execution_result)} instead of (results, failed)")
                agent_results = []
                failed_agents = []

            # Debug: Check agent_results before aggregation
            logger.info(f"DEBUG: agent_results type: {type(agent_results)}, length: {len(agent_results) if agent_results else 'None'}")

            # Step 4: Aggregate agent signals
            aggregated_analysis = self._aggregate_results(agent_results)

            # Step 5: Generate FINAL JUDGE decision (LLM-backed) using full agent + position context
            if not self.agents:
                # Stub behavior when no agents configured (for backward compatibility)
                logger.warning(f"ORCHESTRATOR: No agents configured, using stub behavior")
                final_decision = AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={
                        "reasoning": "Stub orchestrator - not yet implemented",
                        "instrument": instrument,
                        "timestamp": timestamp.isoformat(),
                        "agents_run": len(self.agents),
                    },
                )
            else:
                try:
                    # TEMPORARY: Always use fallback decision for faster response
                    # TODO: Fix LLM configuration and re-enable
                    logger.info(f"ORCHESTRATOR: Using fallback decision (LLM temporarily disabled)")

                    print("🎯 ORCHESTRATOR: Generating fallback decision...")
                    # Generate initial decision
                    initial_decision = self._generate_fallback_decision(aggregated_analysis, market_hours, agent_results, failed_agents)
                    print(f"🎯 ORCHESTRATOR: Initial decision: {initial_decision.decision}")

                    # Apply portfolio risk controls
                    print("🎯 ORCHESTRATOR: Applying portfolio risk controls...")
                    final_decision = self._apply_portfolio_risk_controls(
                        initial_decision, instrument, position_data, market_data
                    )
                    print(f"🎯 ORCHESTRATOR: Final decision: {final_decision.decision}")

                    logger.info(f"Portfolio risk assessment: {initial_decision.decision} -> {final_decision.decision}")
                    if initial_decision.decision != final_decision.decision:
                        logger.warning(f"⚠️ Decision modified by risk controls: {initial_decision.decision} -> {final_decision.decision}")
                except Exception as e:
                    print(f"🎯 ORCHESTRATOR: ERROR in decision generation: {e}")
                    import traceback
                    traceback.print_exc()
                    # Create fallback decision
                    final_decision = AnalysisResult(
                        decision="HOLD",
                        confidence=0.0,
                        details={"error": f"Decision generation failed: {e}"}
                    )

            # Step 5.7: Run ExecutionAgent to validate final decision
            print("🎯 ORCHESTRATOR: REACHED EXECUTIONAGENT SECTION!")
            print(f"🎯 ORCHESTRATOR: Final decision is: {final_decision.decision}")
            print("🎯 ORCHESTRATOR: Looking for ExecutionAgent...")
            execution_agent = None
            agent_names = [getattr(a, '_agent_name', a.__class__.__name__) for a in self.agents]
            print(f"🎯 ORCHESTRATOR: Agent list: {agent_names}")

            for agent in self.agents:
                agent_name = getattr(agent, '_agent_name', agent.__class__.__name__)
                print(f"🎯 ORCHESTRATOR: Checking agent: {agent_name}")
                if agent_name == 'ExecutionAgent':
                    execution_agent = agent
                    print("🎯 ORCHESTRATOR: Found ExecutionAgent!")
                    break

            if execution_agent:
                print("🎯 ORCHESTRATOR: Running ExecutionAgent to validate final decision")
                execution_context = {
                    **context,
                    "orchestrator_decision": {
                        "decision": final_decision.decision,
                        "confidence": final_decision.confidence,
                        "timestamp": timestamp.isoformat()
                    },
                    "final_decision": final_decision.decision,
                    "aggregated_analysis": aggregated_analysis,
                    "agent_results": agent_results
                }

                try:
                    print(f"🎯 ORCHESTRATOR: Calling ExecutionAgent.analyze()")
                    execution_result = await execution_agent.analyze(execution_context)
                    print(f"🎯 ORCHESTRATOR: ExecutionAgent returned: {execution_result.decision} ({execution_result.confidence})")
                    print(f"🎯 ORCHESTRATOR: ExecutionAgent reasoning: {execution_result.details.get('reasoning', 'NO REASONING')[:100]}...")
                    logger.info(f"ExecutionAgent result: {execution_result.decision} ({execution_result.confidence})")

                    # Add execution result to final decision details
                    final_decision.details["execution_validation"] = {
                        "decision": execution_result.decision,
                        "confidence": execution_result.confidence,
                        "reasoning": execution_result.details.get("reasoning", "No execution reasoning"),
                        "status": execution_result.details.get("execution_status", "UNKNOWN")
                    }

                    # Save ExecutionAgent result to MongoDB
                    await self._save_agent_decisions_to_mongodb([execution_result], instrument, context)

                except Exception as exec_error:
                    logger.error(f"ExecutionAgent failed: {exec_error}")
                    final_decision.details["execution_error"] = str(exec_error)
            else:
                logger.warning("ExecutionAgent not found in agent list")

            # Step 6: Add metadata and return
            from datetime import timezone
            now = datetime.now(timezone.utc)
            final_decision.details.update({
                "instrument": instrument,
                "timestamp": timestamp.isoformat(),
                "market_hours": market_hours,
                "cycle_interval": cycle_interval,
                "agents_run": len(agent_results),
                "data_points": len(market_data.get("ohlc", [])),
                "options_expiries": len(options_chain.get("expiries", [])) if options_chain else 0,
                "analysis_duration_seconds": (now - timestamp).total_seconds()
            })

            logger.info(f"Completed analysis cycle: {final_decision.decision} "
                       f"(confidence: {final_decision.confidence:.1%})")

            print(f"🎯 ORCHESTRATOR: Analysis cycle COMPLETED, returning {final_decision.decision}")

            # Step 5.5: Publish agent analysis results to Redis for dashboard
            try:
                await self._publish_agent_analysis_results(agent_results, instrument, context)
            except Exception as pub_err:
                logger.warning(f"Failed to publish agent analysis to Redis: {pub_err}")

            # Step 5.6: Save detailed agent analysis to MongoDB for dashboard
            try:
                await self._save_agent_decisions_to_mongodb(agent_results, instrument, context)
            except Exception as save_err:
                logger.warning(f"Failed to save agent decisions to MongoDB: {save_err}")

            # Step 5.6: Publish orchestrator decision to Redis for dashboard
            try:
                await self._publish_orchestrator_decision(final_decision, agent_results, instrument, context)
            except Exception as pub_err:
                logger.warning(f"Failed to publish orchestrator decision to Redis: {pub_err}")

            # Step 6: Create conditional signals from decision (NEW)
            if final_decision.decision != "HOLD" and final_decision.decision != "ERROR":
                try:
                    await self._create_signals_from_decision(
                        final_decision,
                        instrument,
                        market_data.get("current_price"),
                        technical_data.get("technical_indicators", {}) if technical_data else {}
                    )
                except Exception as signal_error:
                    logger.error(f"Failed to create signals from decision: {signal_error}", exc_info=True)
                    final_decision.details["signal_creation_error"] = str(signal_error)

            # Step 7: Execute trading decision if position manager available (immediate execution option)
            if self.position_manager and final_decision.decision != "HOLD" and self.config.get("auto_execute", False):
                try:
                    execution_result = await self.position_manager.execute_trading_decision(
                        instrument=instrument,
                        decision=final_decision.decision,
                        confidence=final_decision.confidence,
                        analysis_details=final_decision.details
                    )
                    final_decision.details["execution_result"] = execution_result
                    logger.info(f"Executed trading decision: {execution_result}")
                except Exception as exec_error:
                    logger.error(f"Failed to execute trading decision: {exec_error}")
                    final_decision.details["execution_error"] = str(exec_error)

            return final_decision

        except Exception as e:
            logger.error(f"Orchestrator cycle failed for {instrument}: {e}")
            return AnalysisResult(
                decision="ERROR",
                confidence=0.0,
                details={
                    "error": str(e),
                    "instrument": instrument,
                    "timestamp": timestamp.isoformat(),
                    "recovery_action": "Check data sources and agent health"
                }
            )

    async def _on_signal_triggered(self, event: Any) -> None:
        """Callback invoked by SignalMonitor when a signal triggers.

        This is the bridge from *signal intent* -> *trade execution*.
        It remains loosely coupled: SignalMonitor calls us, and we call PositionManagerProvider.
        """
        try:
            # Lazy import to avoid circular deps in some test contexts
            from .signal_creator import mark_signal_status
        except Exception:
            mark_signal_status = None

        # Safety switches
        dry_run = bool(self.config.get("auto_execute_dry_run", False))

        instrument = getattr(event, "instrument", None) or ""
        action = getattr(event, "action", None) or "HOLD"
        confidence = float(getattr(event, "confidence", 0.0) or 0.0)
        current_price = float(getattr(event, "current_price", 0.0) or 0.0)
        stop_loss = getattr(event, "stop_loss", None)
        take_profit = getattr(event, "take_profit", None)
        position_size = getattr(event, "position_size", 1.0)

        # Convert signal position_size (float) to integer quantity for PositionManager
        qty = 1
        try:
            qty = max(1, int(round(float(position_size))))
        except Exception:
            qty = 1

        if mark_signal_status:
            try:
                # Mark executed immediately in dry-run (no broker call)
                if dry_run:
                    await mark_signal_status(
                        getattr(event, "condition_id", ""),
                        "executed",
                        mongo_db=self.mongo_db,
                        extra={"dry_run": True, "executed_at": datetime.utcnow().isoformat()},
                    )
                    logger.info(f"Auto-execute dry-run: would execute {action} {instrument} @ {current_price}")
                    return
            except Exception:
                pass

        # Execute via PositionManagerProvider
        if not self.position_manager:
            return

        try:
            execution_result = await self.position_manager.execute_trading_decision(
                instrument=instrument,
                decision=action,
                confidence=confidence,
                analysis_details={
                    "current_price": current_price,
                    "entry_price": current_price,
                    "quantity": qty,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "signal_id": getattr(event, "condition_id", None),
                },
            )

            if mark_signal_status:
                try:
                    await mark_signal_status(
                        getattr(event, "condition_id", ""),
                        "executed",
                        mongo_db=self.mongo_db,
                        extra={
                            "executed_at": datetime.utcnow().isoformat(),
                            "execution_result": execution_result,
                        },
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Auto-execute failed for signal {getattr(event, 'condition_id', '')}: {e}", exc_info=True)

    async def _fetch_market_data(self, instrument: str) -> Dict[str, Any]:
        """Fetch comprehensive market data for analysis."""
        try:
            # Use the market_data_provider if available
            if self.market_data_provider and hasattr(self.market_data_provider, 'get_ohlc_data'):
                # New Redis-based provider
                ohlc_data = await self.market_data_provider.get_ohlc_data(instrument, periods=100)
                
                # Get REAL-TIME current price from Redis tick data (not stale OHLC close)
                current_price = None
                try:
                    # Try to get latest tick price from Redis (real-time)
                    import redis
                    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
                    instrument_clean = instrument.upper().replace(" ", "").replace("-", "_")
                    
                    # Try key variations (BANKNIFTY vs NIFTYBANK)
                    key_variations = [
                        instrument_clean,
                        instrument_clean.replace("BANKNIFTY", "NIFTYBANK"),
                        instrument_clean.replace("NIFTYBANK", "BANKNIFTY"),
                    ]
                    
                    for key_var in key_variations:
                        price_key = f"price:{key_var}:last_price"
                        price_str = redis_client.get(price_key)
                        if price_str:
                            current_price = float(price_str)
                            break
                    
                    # If price key doesn't exist, try tick:latest format
                    if current_price is None:
                        for key_var in key_variations:
                            tick_key = f"tick:{key_var}:latest"
                            tick_data = redis_client.get(tick_key)
                            if tick_data:
                                import json
                                tick = json.loads(tick_data)
                                if isinstance(tick, dict) and 'last_price' in tick:
                                    current_price = float(tick['last_price'])
                                    break
                                elif isinstance(tick, dict) and 'price' in tick:
                                    current_price = float(tick['price'])
                                    break
                    
                except Exception as redis_err:
                    logger.debug(f"Could not get real-time price from Redis: {redis_err}")
                    current_price = None
                
                # Fallback to OHLC close if tick price not available (less ideal but better than 0)
                if current_price is None or current_price <= 0:
                    current_price = ohlc_data[-1].get('close', 0) if ohlc_data else 0
                    if current_price > 0:
                        logger.debug(f"Using OHLC close price {current_price} as fallback (tick data unavailable)")
                
                return {
                    "instrument": instrument,
                    "ticks": [],  # Not available from Redis provider
                    "ohlc": ohlc_data,
                    "current_price": current_price,  # [OK] Now uses real-time tick price
                    "data_freshness": datetime.utcnow().isoformat()
                }
            elif hasattr(self, 'market_store') and self.market_store:
                # Legacy market_store
                ticks = await self.market_store.get_latest_ticks(instrument, limit=100)
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=24)
                ohlc_data = await self.market_store.get_ohlc(instrument, "15min", start_time, end_time)
                ohlc_list = list(ohlc_data) if hasattr(ohlc_data, '__iter__') else []
                return {
                    "instrument": instrument,
                    "ticks": ticks or [],
                    "ohlc": ohlc_list,
                    "current_price": ticks[0].last_price if ticks else None,
                    "data_freshness": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "instrument": instrument,
                    "ticks": [],
                    "ohlc": [],
                    "error": "No market data provider available"
                }

        except Exception as e:
            logger.warning(f"Failed to fetch market data for {instrument}: {e}")
            return {
                "instrument": instrument,
                "ticks": [],
                "ohlc": [],
                "error": str(e)
            }

    async def _fetch_options_data(self, instrument: str) -> Dict[str, Any]:
        """Fetch options chain data for strategy analysis."""
        try:
            # Use the options_data_provider if available
            if self.options_data_provider and hasattr(self.options_data_provider, 'fetch_chain'):
                chain_data = await self.options_data_provider.fetch_chain(instrument)
            elif hasattr(self, 'options_data') and self.options_data:
                # Legacy options_data
                chain_data = await self.options_data.fetch_chain(instrument)
            else:
                chain_data = {}

            return {
                "instrument": instrument,
                "expiries": chain_data.get("expiries", []),
                "calls": chain_data.get("calls", []),
                "puts": chain_data.get("puts", []),
                "underlying_price": chain_data.get("underlying_price"),
                "pcr": chain_data.get("pcr", 0.0),
                "max_pain": chain_data.get("max_pain")
            }

        except Exception as e:
            logger.warning(f"Failed to fetch options data for {instrument}: {e}")
            return {
                "instrument": instrument,
                "expiries": [],
                "calls": [],
                "puts": [],
                "error": str(e)
            }

    async def _fetch_news_data(self, instrument: str) -> Dict[str, Any]:
        """Fetch news data for sentiment analysis."""
        if not self.news_service:
            return {
                "instrument": instrument,
                "latest_news": [],
                "sentiment_summary": {},
                "news_available": False
            }

        try:
            # Ensure news service is initialized (for RSS collector)
            if hasattr(self.news_service, '__aenter__'):
                await self.news_service.__aenter__()
            
            # Get latest news for the instrument
            latest_news = await self.news_service.get_latest_news(instrument, limit=10)

            # Get sentiment summary for the last 24 hours
            sentiment_summary_obj = await self.news_service.get_sentiment_summary(instrument, hours=24)
            
            # Convert to dict for easier access (handle both dicts and dataclass instances)
            import dataclasses
            if isinstance(sentiment_summary_obj, dict):
                sentiment_summary = sentiment_summary_obj
            elif sentiment_summary_obj and dataclasses.is_dataclass(sentiment_summary_obj):
                sentiment_summary = dataclasses.asdict(sentiment_summary_obj)
            else:
                sentiment_summary = {}

            # Extract aggregate sentiment score for agents
            aggregate_sentiment = sentiment_summary.get("average_sentiment", 0.0)

            # Convert news items to dicts (handle both dicts and dataclass instances)
            news_dicts = []
            for item in latest_news:
                if isinstance(item, dict):
                    news_dicts.append(item)
                elif dataclasses.is_dataclass(item):
                    news_dicts.append(dataclasses.asdict(item))
                else:
                    news_dicts.append(dict(item) if hasattr(item, '__dict__') else {})

            return {
                "instrument": instrument,
                "latest_news": news_dicts,
                "sentiment_summary": sentiment_summary,
                "sentiment_score": aggregate_sentiment,
                "news_available": True
            }

        except Exception as e:
            logger.warning(f"Failed to fetch news data for {instrument}: {e}")
            return {
                "instrument": instrument,
                "latest_news": [],
                "sentiment_summary": {},
                "sentiment_score": 0.0,
                "news_available": False,
                "error": str(e)
            }

    async def _fetch_macro_data(self, instrument: str) -> Dict[str, Any]:
        """Fetch macroeconomic data for analysis."""
        if not self.macro_data_provider:
            return {
                "instrument": instrument,
                "rbi_rate": None,
                "inflation_rate": None,
                "npa_ratio": None,
                "macro_data_available": False
            }

        try:
            # Get RBI repo rate (latest)
            rbi_data = await self.macro_data_provider.get_rbi_data("repo_rate", days=1)
            rbi_rate = rbi_data[-1].value if rbi_data else None

            # Get inflation data (latest monthly)
            inflation_data = await self.macro_data_provider.get_inflation_data(months=1)
            inflation_rate = inflation_data[-1].value if inflation_data else None

            # Get NPA ratio (latest quarterly)
            npa_data = await self.macro_data_provider.get_rbi_data("npa_ratio", days=90)
            npa_ratio = npa_data[-1].value if npa_data else None

            return {
                "instrument": instrument,
                "rbi_rate": rbi_rate,
                "inflation_rate": inflation_rate,
                "npa_ratio": npa_ratio,
                "macro_data_available": True
            }

        except Exception as e:
            logger.warning(f"Failed to fetch macro data for {instrument}: {e}")
            return {
                "instrument": instrument,
                "rbi_rate": None,
                "inflation_rate": None,
                "npa_ratio": None,
                "macro_data_available": False,
                "error": str(e)
            }

    async def _fetch_technical_data(self, instrument: str) -> Dict[str, Any]:
        """Fetch technical indicators data."""
        if not self.technical_data_provider:
            return {
                "instrument": instrument,
                "technical_indicators": {},
                "technical_data_available": False
            }

        try:
            # Get technical indicators
            print(f"[DEBUG] Orchestrator calling get_technical_indicators for {instrument}")
            technical_indicators = await self.technical_data_provider.get_technical_indicators(instrument, periods=100)
            print(f"[DEBUG] Orchestrator received indicators: {type(technical_indicators)}")

            if technical_indicators is None:
                return {
                    "instrument": instrument,
                    "technical_indicators": {},
                    "technical_data_available": False
                }

            # Convert to dict for easier access
            # Handle both dataclass instances and dicts
            import dataclasses
            if isinstance(technical_indicators, dict):
                indicators_dict = technical_indicators
            elif dataclasses.is_dataclass(technical_indicators):
                indicators_dict = dataclasses.asdict(technical_indicators)
            else:
                # Fallback: try to convert to dict
                indicators_dict = dict(technical_indicators) if hasattr(technical_indicators, '__dict__') else {}

            return {
                "instrument": instrument,
                "technical_indicators": indicators_dict,
                "technical_data_available": True
            }

        except Exception as e:
            logger.warning(f"Failed to fetch technical data for {instrument}: {e}")
            return {
                "instrument": instrument,
                "technical_indicators": {},
                "technical_data_available": False,
                "error": str(e)
            }
        finally:
            # Cleanup news service
            if hasattr(self.news_service, '__aexit__'):
                await self.news_service.__aexit__(None, None, None)

    async def _fetch_position_data(self, instrument: str) -> Dict[str, Any]:
        """Fetch position data for the instrument."""
        if not self.position_manager:
            return {
                "instrument": instrument,
                "positions": [],
                "portfolio_summary": {},
                "position_data_available": False
            }

        try:
            # Get current positions for this instrument
            positions = await self.position_manager.get_positions(instrument)
            
            # Get portfolio summary
            portfolio_summary = self.position_manager.get_portfolio_summary()

            # Convert positions to dict for easier access (handle both dicts and dataclass instances)
            import dataclasses
            positions_dict = []
            for pos in positions:
                if isinstance(pos, dict):
                    positions_dict.append(pos)
                elif pos and dataclasses.is_dataclass(pos):
                    positions_dict.append(dataclasses.asdict(pos))
                else:
                    positions_dict.append(dict(pos) if hasattr(pos, '__dict__') else {})

            # Convert portfolio summary
            portfolio_dict = {}
            if portfolio_summary:
                if isinstance(portfolio_summary, dict):
                    portfolio_dict = portfolio_summary
                elif dataclasses.is_dataclass(portfolio_summary):
                    portfolio_dict = dataclasses.asdict(portfolio_summary)
                else:
                    portfolio_dict = dict(portfolio_summary) if hasattr(portfolio_summary, '__dict__') else {}

            return {
                "instrument": instrument,
                "positions": positions_dict,
                "portfolio_summary": portfolio_dict,
                "position_data_available": True
            }

        except Exception as e:
            logger.warning(f"Failed to fetch position data for {instrument}: {e}")
            return {
                "instrument": instrument,
                "positions": [],
                "portfolio_summary": {},
                "position_data_available": False,
                "error": str(e)
            }

    async def _run_agents_parallel(self, market_data: Dict[str, Any],
                                 options_data: Dict[str, Any],
                                 news_data: Dict[str, Any],
                                 technical_data: Dict[str, Any],
                                 macro_data: Dict[str, Any],
                                 position_data: Dict[str, Any],
                                 context: Dict[str, Any]) -> tuple[list[AnalysisResult], list]:
        """Run all agents in parallel and collect their results."""
        if not self.agents:
            logger.warning("No agents configured for orchestrator")
            return [], []

        logger.info(f"Starting parallel agent execution with {len(self.agents)} agents")
        agent_names = [getattr(a, '_agent_name', a.__class__.__name__) for a in self.agents]
        logger.info(f"Agent names: {agent_names}")

        # Prepare context for agents
        logger.debug(f"Context types - market_data: {type(market_data)}, options_data: {type(options_data)}, news_data: {type(news_data)}, technical_data: {type(technical_data)}, macro_data: {type(macro_data)}, position_data: {type(position_data)}")

        # Ensure all data variables are dicts (not None)
        market_data = market_data or {}
        options_data = options_data or {}
        news_data = news_data or {}
        technical_data = technical_data or {}
        macro_data = macro_data or {}
        position_data = position_data or {}

        agent_context = {
            **context,
            **market_data,
            **options_data,
            **news_data,
            **technical_data,
            **macro_data,
            **position_data,
            "options_chain": options_data,  # Alias for backward compatibility
            "market_data": market_data,      # Alias for backward compatibility
            "news_data": news_data,          # Alias for backward compatibility
            "technical_data": technical_data, # Alias for backward compatibility
            "macro_data": macro_data,        # Alias for backward compatibility
            "position_data": position_data   # Alias for backward compatibility
        }

        # Debug logging for agent context
        # logger.info(f"Agent context keys: {list(agent_context.keys())}")
        # logger.info(f"Technical data available: {'technical_indicators' in agent_context and bool(agent_context.get('technical_indicators'))}")
        # logger.info(f"Market data available: {'current_price' in agent_context and agent_context.get('current_price', 0) > 0}")

        # Pre-flight health check for agents
        healthy_agents = await self._check_agent_health(agent_context)

        if len(healthy_agents) != len(self.agents):
            unhealthy_count = len(self.agents) - len(healthy_agents)
            logger.warning(f"⚠️ Agent health check: {unhealthy_count} agents failed pre-flight check")

        if not healthy_agents:
            logger.error("❌ CRITICAL: All agents failed health check - aborting analysis cycle")
            raise RuntimeError("All agents failed health check - unable to perform analysis")

        # Run healthy agents concurrently with retry logic
        logger.info(f"Running {len(healthy_agents)} healthy agents concurrently with retry support")
        tasks = [self._run_agent_with_retry(agent, agent_context) for agent in healthy_agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log errors; attach agent identity to results
        valid_results = []
        failed_agents = []

        logger.info(f"DEBUG: Starting result filtering for {len(results)} raw results")
        for i, result in enumerate(results):
            agent_obj = self.agents[i]
            agent_name = getattr(agent_obj, '_agent_name', agent_obj.__class__.__name__)
            if isinstance(result, Exception):
                logger.error(f"❌ Agent {agent_name} failed: {result}")
                # Record failed agent for gap handling instead of synthetic data
                failed_agents.append({
                    "agent": agent_name,
                    "error": str(result),
                    "error_type": type(result).__name__
                })
                # Don't create synthetic fallback result - prefer gaps over bad data
                continue
            else:
                # Attach agent name into AnalysisResult and details for persistence
                try:
                    result.agent = agent_name
                    if result.details is None:
                        result.details = {}
                    # don't overwrite existing agent field in details
                    result.details.setdefault('agent', agent_name)
                    valid_results.append(result)
                    logger.debug(f"[OK] Agent {agent_name} succeeded: decision={result.decision} confidence={result.confidence}")
                except Exception as e:
                    logger.exception(f"Failed to attach agent metadata for {agent_name}: {e}")
                    # still include the result to avoid losing data
                    valid_results.append(result)

        # Log summary of agent execution
        total_agents = len(self.agents)
        successful_agents = len(valid_results)
        failed_count = len(failed_agents)

        if failed_count > 0:
            logger.warning(f"⚠️ Agent execution summary: {successful_agents}/{total_agents} agents succeeded, {failed_count} failed")
            for failure in failed_agents:
                logger.warning(f"   - {failure['agent']}: {failure['error_type']} - {failure['error'][:100]}...")
        else:
            logger.info(f"[OK] All {total_agents} agents executed successfully")

        # Check if we should run ExecutionAgent for final validation
        # This handles cases where _run_agents_parallel is called directly
        if valid_results and len(valid_results) > 0:
            # Try to find and run ExecutionAgent
            execution_agent = None
            for agent in self.agents:
                agent_name = getattr(agent, '_agent_name', agent.__class__.__name__)
                if agent_name == 'ExecutionAgent':
                    execution_agent = agent
                    break

            if execution_agent and not any(r.agent == 'ExecutionAgent' for r in valid_results if hasattr(r, 'agent')):
                logger.info("Running ExecutionAgent for final validation")
                try:
                    # Generate aggregated analysis
                    aggregated = self._aggregate_results(valid_results)

                    # Create execution context
                    execution_context = {
                        **context,
                        "orchestrator_decision": {
                            "decision": aggregated.get('options_strategy', 'HOLD'),
                            "confidence": aggregated.get('confidence_score', 0.0)
                        },
                        "aggregated_analysis": aggregated,
                        "agent_results": valid_results
                    }

                    execution_result = await execution_agent.analyze(execution_context)
                    logger.info(f"ExecutionAgent validated: {execution_result.decision} ({execution_result.confidence})")

                    # Add ExecutionAgent result to valid results
                    execution_result.agent = 'ExecutionAgent'
                    valid_results.append(execution_result)

                except Exception as exec_error:
                    logger.error(f"ExecutionAgent validation failed: {exec_error}")

        # Debug logging before return
        try:
            logger.info(f"DEBUG: About to return from _run_agents_parallel")
            logger.info(f"DEBUG: valid_results is {type(valid_results)}, failed_agents is {type(failed_agents)}")
            if valid_results is not None:
                logger.info(f"DEBUG: valid_results length: {len(valid_results)}")
            if failed_agents is not None:
                logger.info(f"DEBUG: failed_agents length: {len(failed_agents)}")
        except Exception as debug_e:
            logger.error(f"DEBUG logging failed: {debug_e}")

        return valid_results, failed_agents

    async def _run_agent_with_retry(self, agent, context: Dict[str, Any], max_retries: int = 2) -> Any:
        """Run a single agent with retry logic, exponential backoff, and rate limiting.

        Args:
            agent: Agent instance to run
            context: Analysis context
            max_retries: Maximum number of retry attempts

        Returns:
            AnalysisResult or Exception if all retries failed
        """
        agent_name = getattr(agent, '_agent_name', agent.__class__.__name__)

        async with self._agent_semaphore:  # Rate limiting
            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    # Add rate limiting jitter for concurrent calls
                    if attempt > 0:
                        import random
                        import time
                        # Exponential backoff with jitter: 0.5, 1.0, 2.0 seconds + random jitter
                        delay = (0.5 * (2 ** (attempt - 1))) + random.uniform(0.1, 0.5)
                        logger.info(f"🔄 Retrying {agent_name} in {delay:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                        await asyncio.sleep(delay)

                    result = await agent.analyze(context)
                    if attempt > 0:
                        logger.info(f"[OK] {agent_name} recovered on retry {attempt + 1}")
                    return result

                except Exception as e:
                    error_type = type(e).__name__
                    error_msg = str(e)

                    if attempt < max_retries:
                        # Check if this is a recoverable error
                        recoverable_errors = [
                            "RateLimitError", "TimeoutError", "ConnectionError",
                            "HTTPError", "NetworkError", "APITimeout"
                        ]

                        is_recoverable = any(recoverable in error_type for recoverable in recoverable_errors) or \
                                        any(recoverable.lower() in error_msg.lower() for recoverable in recoverable_errors)

                        if is_recoverable:
                            logger.warning(f"⚠️ {agent_name} failed (recoverable): {error_type} - {error_msg[:100]}...")
                            continue  # Retry
                        else:
                            logger.error(f"❌ {agent_name} failed (non-recoverable): {error_type} - {error_msg[:100]}...")
                            break  # Don't retry
                    else:
                        logger.error(f"❌ {agent_name} failed after {max_retries + 1} attempts: {error_type} - {error_msg[:100]}...")
                        break  # All retries exhausted

                # All attempts failed - return the last exception
                return RuntimeError(f"{agent_name} failed after {max_retries + 1} attempts")

    async def _check_agent_health(self, context: Dict[str, Any]) -> list:
        """Perform pre-flight health checks on agents.

        Args:
            context: Analysis context

        Returns:
            List of healthy agents
        """
        healthy_agents = []
        unhealthy_agents = []

        for agent in self.agents:
            agent_name = getattr(agent, '_agent_name', agent.__class__.__name__)

            try:
                # Quick health check - try to access basic agent attributes
                if not hasattr(agent, 'analyze'):
                    raise AttributeError(f"Agent {agent_name} missing analyze method")

                # Optional: Try a minimal analysis call with timeout
                # This helps catch agents that immediately fail due to config issues
                try:
                    import asyncio
                    health_check_task = asyncio.create_task(
                        asyncio.wait_for(agent.analyze(context), timeout=2.0)
                    )
                    # Don't wait for completion, just check if it starts
                    await asyncio.sleep(0.1)  # Brief pause to let task start

                    if not health_check_task.done():
                        health_check_task.cancel()  # Cancel the health check
                        healthy_agents.append(agent)
                        logger.debug(f"[OK] Agent {agent_name} health check passed")
                    else:
                        # Task completed quickly - check if it succeeded or failed
                        try:
                            result = health_check_task.result()
                            healthy_agents.append(agent)
                            logger.debug(f"[OK] Agent {agent_name} quick health check passed")
                        except Exception as e:
                            unhealthy_agents.append((agent_name, str(e)))
                            logger.warning(f"⚠️ Agent {agent_name} failed quick health check: {e}")
                except asyncio.TimeoutError:
                    # Timeout is actually good - means agent started processing
                    healthy_agents.append(agent)
                    logger.debug(f"[OK] Agent {agent_name} health check passed (processing)")
                except Exception as e:
                    unhealthy_agents.append((agent_name, str(e)))
                    logger.warning(f"⚠️ Agent {agent_name} health check failed: {e}")

            except Exception as e:
                unhealthy_agents.append((agent_name, str(e)))
                logger.error(f"❌ Agent {agent_name} critical health failure: {e}")

        if unhealthy_agents:
            logger.warning(f"Agent health summary: {len(healthy_agents)} healthy, {len(unhealthy_agents)} unhealthy")
            for agent_name, error in unhealthy_agents:
                logger.warning(f"  - {agent_name}: {error}")

        return healthy_agents

        logger.info(f"Agent execution complete: {len(valid_results)}/{len(self.agents)} agents produced results")

        logger.info(f"Successfully ran {len(valid_results)}/{len(self.agents)} agents")

        # Save individual agent decisions to API service for UI display
        if valid_results:
            try:
                await self._save_agent_decisions_to_api(valid_results, instrument)
            except Exception as save_error:
                logger.warning(f"Failed to save agent decisions to API: {save_error}")

        return valid_results

    def _aggregate_results(self, agent_results: list[AnalysisResult]) -> Dict[str, Any]:
        """Aggregate multiple agent results into unified options trading view with weighted voting.

        Weighting Strategy:
        - Analysis Tier (Technical/Sentiment/Macro/Fundamental): 1.5x weight
        - Technical Specialists (Momentum/Trend/Volume/Reversion): 1.0x weight
        - Research Tier (Bull/Bear): 0.5x weight (contrarian views)
        - Risk Agents: 2.0x weight with veto power
        - Execution Agents: 0.0x weight (validators, not voters)
        """
        if agent_results is None:
            logger.error("❌ CRITICAL: agent_results is None in _aggregate_results")
            agent_results = []

        print(f"DEBUG: _aggregate_results called with {len(agent_results)} agent results")
        for i, result in enumerate(agent_results[:3]) if agent_results else []:
            agent_name = getattr(result, 'agent', 'Unknown')
            print(f"DEBUG: Agent {i+1}: {agent_name} -> {result.decision} ({result.confidence})")

        if not agent_results:
            return {
                "signal_strength": 0.0,
                "consensus_direction": "NEUTRAL",
                "confidence_score": 0.0,
                "risk_assessment": "UNKNOWN",
                "key_insights": [],
                "options_strategy": "HOLD",
                "weighted_votes": {"buy": 0, "sell": 0, "hold": 0}
            }

        # Define agent weights by category
        AGENT_WEIGHTS = {
            'technical': 1.5,      # Technical/Sentiment/Macro get higher weight
            'sentiment': 1.5,
            'macro': 1.5,
            'fundamental': 1.5,
            'momentum': 1.0,       # Specialized technical agents
            'trend': 1.0,
            'volume': 1.0,
            'reversion': 1.0,
            'mean_reversion': 1.0,
            'bull': 0.5,           # Bull/Bear researchers get lower weight
            'bear': 0.5,
            'research': 0.5,
            'options': 1.5,        # Options strategy agents get higher weight
            'risk': 2.0,           # Risk agent gets veto power
            'execution': 0.0       # Execution doesn't vote, only validates
        }

        # Initialize weighted aggregation
        buy_signals = 0  # Count
        sell_signals = 0
        hold_signals = 0
        options_signals = 0  # Count for options strategies
        buy_weight = 0.0  # Weighted score
        sell_weight = 0.0
        hold_weight = 0.0
        options_weight = 0.0  # Weighted score for options strategies
        total_weight = 0.0
        total_confidence = 0.0

        technical_signals = []
        sentiment_signals = []
        macro_signals = []
        risk_signals = []
        execution_signals = []
        bull_bear_signals = []

        # Analyze each agent result with weighted voting
        risk_veto_triggered = False
        risk_veto_reason = None
        
        for result in agent_results:
            confidence = result.confidence
            total_confidence += confidence
            
            # Extract agent-specific insights
            agent_name = result.agent if getattr(result, 'agent', None) else getattr(result, '_agent_name', 'Unknown')
            details = result.details or {}
            
            # Determine agent weight based on category
            weight = 1.0  # Default weight
            for category, category_weight in AGENT_WEIGHTS.items():
                if category in agent_name.lower():
                    weight = category_weight
                    break

            # Special handling for options strategy agents
            if 'optionsstrategy' in agent_name.lower().replace(' ', ''):
                weight = AGENT_WEIGHTS.get('options', 1.5)
            
            # RISK VETO: Check if risk agent vetoes the trade
            if 'risk' in agent_name.lower():
                risk_level = details.get('risk_level', 'UNKNOWN')
                if risk_level == 'HIGH':
                    risk_veto_triggered = True
                    risk_veto_reason = details.get('veto_reason', 'High risk detected')
                    logger.warning(f"RISK VETO TRIGGERED by {agent_name}: {risk_veto_reason}")
            
            # Categorize by decision with weighted votes
            decision = result.decision.upper()
            weighted_vote = weight * confidence

            # Check for options strategies first
            if any(strategy in decision for strategy in ["IRON_CONDOR", "BUY_CALL", "BUY_PUT", "BEAR_CALL", "BULL_PUT"]):
                options_signals += 1
                options_weight += weighted_vote
            elif decision == "BUY":
                buy_signals += 1
                buy_weight += weighted_vote
            elif decision == "SELL":
                sell_signals += 1
                sell_weight += weighted_vote
            else:
                hold_signals += 1
                hold_weight += weighted_vote
            
            total_weight += weight
            
            # Categorize signals by agent type
            signal_data = {
                "agent": agent_name,
                "signal": result.decision,
                "confidence": confidence,
                "weight": weight,
                "weighted_vote": weighted_vote
            }
            
            if 'technical' in agent_name.lower() and 'agent' in agent_name.lower():
                # TechnicalAgent (not momentum/trend/etc)
                technical_signals.append({
                    **signal_data,
                    "indicators": details
                })
            elif 'sentiment' in agent_name.lower():
                sentiment_signals.append({
                    **signal_data,
                    "sentiment": details.get('aggregate_sentiment', 0.0)
                })
            elif 'macro' in agent_name.lower():
                macro_signals.append({
                    **signal_data,
                    "indicators": details
                })
            elif 'risk' in agent_name.lower():
                risk_signals.append({
                    **signal_data,
                    "risk_level": details.get('risk_level', 'UNKNOWN')
                })
            elif 'execution' in agent_name.lower():
                execution_signals.append({
                    **signal_data,
                    "execution_readiness": details.get('execution_ready', False)
                })
            elif any(x in agent_name.lower() for x in ['bull', 'bear', 'research']):
                bull_bear_signals.append({
                    **signal_data,
                    "thesis": details.get('thesis', 'N/A')
                })
            else:
                # Specialized technical agents (momentum, trend, volume, reversion)
                technical_signals.append({
                    **signal_data,
                    "indicators": details
                })

        # Calculate consensus
        total_agents = len(agent_results)
        avg_confidence = total_confidence / total_agents if total_agents > 0 else 0.0
        
        # RISK VETO: Override all other signals if risk veto triggered
        if risk_veto_triggered:
            consensus_direction = "HOLD"
            signal_strength = 0.0
            logger.info(f"Consensus overridden to HOLD due to risk veto: {risk_veto_reason}")
        else:
            # Determine weighted consensus direction (including options strategies)
            # Options strategies get priority if they have sufficient confidence
            if options_weight > 0 and (options_weight >= sell_weight and options_weight >= buy_weight):
                # Check if options strategies have sufficient conviction
                avg_options_confidence = options_weight / options_signals if options_signals > 0 else 0
                if avg_options_confidence > 0.5:  # Require >50% average confidence for options
                    consensus_direction = "IRON_CONDOR"  # Default to IRON_CONDOR for now
                else:
                    consensus_direction = "HOLD"
            elif buy_weight > sell_weight and buy_weight > hold_weight:
                consensus_direction = "BUY"
            elif sell_weight > buy_weight and sell_weight > hold_weight:
                consensus_direction = "SELL"
            else:
                consensus_direction = "HOLD"

            # Calculate weighted signal strength (0.0 to 1.0)
            all_weights = [buy_weight, sell_weight, hold_weight, options_weight]
            max_weight = max(all_weights) if all_weights else 0.0
            signal_strength = max_weight / total_weight if total_weight > 0 else 0.0

        # Assess overall risk
        risk_assessment = "LOW"
        if any(sig.get('risk_level') == 'HIGH' for sig in risk_signals):
            risk_assessment = "HIGH"
        elif any(sig.get('risk_level') == 'MEDIUM' for sig in risk_signals):
            risk_assessment = "MEDIUM"

        # Generate options strategy recommendation
        options_strategy = self._recommend_options_strategy(
            consensus_direction, signal_strength, risk_assessment, avg_confidence
        )

        # Compile key insights with weighted voting details
        key_insights = []
        if technical_signals:
            weighted_support = sum(s['weighted_vote'] for s in technical_signals if s['signal'] == consensus_direction)
            key_insights.append(f"Technical: {len([s for s in technical_signals if s['signal'] == consensus_direction])}/{len(technical_signals)} agents support {consensus_direction} (weight: {weighted_support:.2f})")
        if sentiment_signals:
            avg_sentiment = sum(s['sentiment'] for s in sentiment_signals) / len(sentiment_signals)
            key_insights.append(f"Sentiment: {avg_sentiment:.2f} (market mood)")
        if macro_signals:
            key_insights.append(f"Macro: {len([s for s in macro_signals if s['signal'] == consensus_direction])}/{len(macro_signals)} support {consensus_direction}")
        if bull_bear_signals:
            bull_count = len([s for s in bull_bear_signals if 'bull' in s['agent'].lower()])
            bear_count = len([s for s in bull_bear_signals if 'bear' in s['agent'].lower()])
            key_insights.append(f"Research: {bull_count} bullish researchers, {bear_count} bearish researchers (contrarian views)")
        if risk_veto_triggered:
            key_insights.append(f"⚠️ RISK VETO: {risk_veto_reason}")

        return {
            "signal_strength": signal_strength,
            "consensus_direction": consensus_direction,
            "confidence_score": avg_confidence,
            "risk_assessment": risk_assessment,
            "options_strategy": options_strategy,
            "agent_breakdown": {
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "hold_signals": hold_signals,
                "options_signals": options_signals,
                "total_agents": total_agents,
                "total_weight": total_weight
            },
            "weighted_votes": {
                "buy": round(buy_weight, 2),
                "sell": round(sell_weight, 2),
                "hold": round(hold_weight, 2),
                "options": round(options_weight, 2)
            },
            "risk_veto": {
                "triggered": risk_veto_triggered,
                "reason": risk_veto_reason
            },
            "technical_signals": technical_signals,
            "sentiment_signals": sentiment_signals,
            "macro_signals": macro_signals,
            "risk_signals": risk_signals,
            "execution_signals": execution_signals,
            "bull_bear_signals": bull_bear_signals,
            "key_insights": key_insights
        }

    def _recommend_options_strategy(self, direction: str, strength: float,
                                  risk: str, confidence: float) -> str:
        """Recommend options trading strategy based on analysis."""
        if strength < 0.4 or confidence < 0.3:
            return "HOLD - Insufficient conviction"

        if risk == "HIGH":
            return "HOLD - Risk too high for options"

        if direction == "BUY":
            if strength > 0.7 and confidence > 0.7:
                return "BUY_CALL - Strong bullish momentum"
            elif strength > 0.5:
                return "BUY_CALL_SPREAD - Moderate bullish outlook"
            else:
                return "HOLD - Weak bullish signals"

        elif direction == "SELL":
            if strength > 0.7 and confidence > 0.7:
                return "BUY_PUT - Strong bearish momentum"
            elif strength > 0.5:
                return "BUY_PUT_SPREAD - Moderate bearish outlook"
            else:
                return "HOLD - Weak bearish signals"

        else:
            if risk == "LOW":
                return "IRON_CONDOR - Low volatility, collect premium"
            else:
                return "HOLD - Market consolidation"

    async def _generate_llm_decision(
        self,
        aggregated: Dict[str, Any],
        agent_results: list[AnalysisResult],
        position_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> AnalysisResult:
        """Generate final trading decision using an LLM-as-judge.

        The judge must:
        - produce detailed English reasoning
        - be position-aware (entries/exits/hold/scale/reverse)
        - output structured signals (entry + exit) valid for the next cycle
        """
        try:
            prompt = self._build_decision_prompt(aggregated, agent_results, position_data, context)

            # Import here to avoid circular dependencies
            from genai_module.contracts import LLMRequest

            # Use environment variable if set, otherwise let provider use default model
            model_override = os.getenv("LLM_DECISION_MODEL") or os.getenv("LLM_MODEL")
            # Don't pass empty string or invalid model names
            if model_override and model_override.strip():
                # Validate model name (basic check)
                if not any(invalid in model_override.lower() for invalid in ["gpt-5", "gpt-4o-mini-invalid"]):
                    model = model_override
                else:
                    model = None  # Let provider use default
            else:
                model = None  # Let provider use default

            llm_request = LLMRequest(
                prompt=prompt,
                model=model,
                temperature=0.1,  # Low temperature for consistent decisions
                max_tokens=1000
            )

            llm_response = await self.llm_client.generate(llm_request)

            # Parse LLM response
            return self._parse_llm_response(llm_response, aggregated, agent_results, position_data)

        except Exception as e:
            # Log full stack so provider/LLM issues are easier to diagnose
            logger.exception(f"LLM decision generation failed: {e}")
            return self._generate_fallback_decision(aggregated, True)

    def _build_decision_prompt(
        self,
        aggregated: Dict[str, Any],
        agent_results: list[AnalysisResult],
        position_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Build comprehensive LLM prompt for a Final Judge decision.

        Outputs must be (1) human-readable English reasoning, and (2) machine-usable structured signals.
        """
        instrument = context.get("instrument", "BANKNIFTY")  # Default to BANKNIFTY Futures (nearest expiry)
        market_hours = context.get("market_hours", False)
        
        # Extract weighted voting details
        weighted_votes = aggregated.get('weighted_votes', {})
        risk_veto = aggregated.get('risk_veto', {})
        bull_bear_signals = aggregated.get('bull_bear_signals', [])

        # Positions snapshot (judge must be position-aware)
        positions = []
        try:
            if isinstance(position_data, dict) and isinstance(position_data.get("positions"), list):
                positions = position_data.get("positions") or []
        except Exception:
            positions = []

        def _pos_line(p: Dict[str, Any]) -> str:
            try:
                side = p.get("action") or p.get("side") or p.get("position") or "UNKNOWN"
                qty = p.get("quantity") or p.get("qty") or "?"
                entry = p.get("entry_price") or p.get("avg_price") or "?"
                cur = p.get("current_price") or p.get("ltp") or "?"
                sl = p.get("stop_loss") or p.get("sl") or ""
                tp = p.get("take_profit") or p.get("tp") or ""
                return f"- side={side}, qty={qty}, entry={entry}, current={cur}, stop_loss={sl}, take_profit={tp}"
            except Exception:
                return "- (unparseable position)"

        positions_block = "No open positions." if not positions else "\n".join(_pos_line(p) for p in positions[:10])

        # Agent reports: require English reasoning and evidence-based inputs
        agent_lines = []
        for r in agent_results:
            an = getattr(r, "agent", None) or "UnknownAgent"
            dec = getattr(r, "decision", "HOLD")
            conf = getattr(r, "confidence", 0.0)
            det = getattr(r, "details", {}) or {}
            reasoning = ""
            if isinstance(det, dict):
                reasoning = det.get("reasoning") or det.get("summary") or ""
                # If structured_report exists, try summary
                sr = det.get("structured_report")
                if not reasoning and isinstance(sr, dict):
                    reasoning = sr.get("summary") or ""
            if not reasoning:
                reasoning = "No explicit reasoning provided. Infer based on indicators and decision."
            agent_lines.append(f"- {an}: decision={dec}, confidence={conf:.2f}, reasoning={reasoning}")

        agent_block = "\n".join(agent_lines) if agent_lines else "- (no agent outputs)"

        prompt = f"""You are the FINAL JUDGE for a trading system analyzing {instrument} for the next 15 minutes.

MARKET ANALYSIS SUMMARY:
- Signal Strength: {aggregated['signal_strength']:.1%}
- Consensus Direction: {aggregated['consensus_direction']}
- Average Confidence: {aggregated['confidence_score']:.1%}
- Risk Assessment: {aggregated['risk_assessment']}
- Agent Breakdown: {aggregated['agent_breakdown']['buy_signals']} BUY, {aggregated['agent_breakdown']['sell_signals']} SELL, {aggregated['agent_breakdown']['hold_signals']} HOLD
- Total Agents: {aggregated['agent_breakdown']['total_agents']}

WEIGHTED VOTING RESULTS:
- BUY Weight: {weighted_votes.get('buy', 0):.2f}
- SELL Weight: {weighted_votes.get('sell', 0):.2f}
- HOLD Weight: {weighted_votes.get('hold', 0):.2f}
- Total Weight: {aggregated['agent_breakdown'].get('total_weight', 0):.2f}

CURRENT POSITIONS (MUST BE CONSIDERED):
{positions_block}

AGENT REPORTS (USE THESE AS INPUTS; PRODUCE YOUR OWN DETAILED ENGLISH REASONING):
{agent_block}

KEY INSIGHTS:
{chr(10).join(f"- {insight}" for insight in aggregated['key_insights'])}

TECHNICAL ANALYSIS:
{chr(10).join(f"- {sig['agent']}: {sig['signal']} ({sig['confidence']:.1%}, weight: {sig.get('weight', 1.0):.1f}x)" for sig in aggregated['technical_signals'][:5])}

SENTIMENT ANALYSIS:
{chr(10).join(f"- {sig['agent']}: {sig['signal']} (sentiment: {sig['sentiment']:.2f}, weight: {sig.get('weight', 1.0):.1f}x)" for sig in aggregated['sentiment_signals'][:3])}

MACRO ANALYSIS:
{chr(10).join(f"- {sig['agent']}: {sig['signal']} ({sig['confidence']:.1%}, weight: {sig.get('weight', 1.0):.1f}x)" for sig in aggregated['macro_signals'][:3])}"""

        # Add Bull/Bear research if available
        if bull_bear_signals:
            prompt += f"""

RESEARCH INSIGHTS (Contrarian Views):
{chr(10).join(f"- {sig['agent']}: {sig['signal']} - {sig.get('thesis', 'N/A')} (weight: {sig.get('weight', 0.5):.1f}x)" for sig in bull_bear_signals)}"""

        prompt += f"""

RISK ASSESSMENT:
{chr(10).join(f"- {sig['agent']}: {sig['signal']} (risk: {sig.get('risk_level', 'UNKNOWN')}, weight: {sig.get('weight', 2.0):.1f}x)" for sig in aggregated['risk_signals'][:2])}"""

        # Add risk veto warning if triggered
        if risk_veto.get('triggered'):
            prompt += f"""

⚠️ RISK VETO TRIGGERED: {risk_veto.get('reason', 'High risk detected')}
All trading signals have been overridden to HOLD due to risk management protocols."""

        prompt += f"""

CURRENT RECOMMENDATION: {aggregated['options_strategy']}

INSTRUCTIONS:
1. Analyze all signals with consideration for their weighted importance
2. Note that Analysis Tier agents (Technical/Sentiment/Macro) have 1.5x weight
3. Technical Specialists (Momentum/Trend/Volume/Reversion) have 1.0x weight  
4. Research agents (Bull/Bear) have 0.5x weight as contrarian views
5. Risk agents have 2.0x weight and can VETO trades
6. Consider market hours: {'OPEN' if market_hours else 'CLOSED'}
7. Factor in risk assessment and position sizing
8. Be position-aware:
   - if already in position, decide HOLD/EXIT/SCALE/REVERSE and emit exit signals
   - if flat, decide whether to enter and emit entry signals
9. A \"signal\" is an intent that may become a trade later:
   - generate signals valid_for_minutes=15 (invalidate previous ones)
   - conditional signals trigger only when conditions are met
10. Every ENTRY must include stop_loss and take_profit (numeric if possible).

Respond in this exact JSON format ONLY (no prose outside JSON):
{{
  "final_decision": "BUY|SELL|HOLD|CLOSE_LONG|CLOSE_SHORT|SCALE_IN|SCALE_OUT|REVERSE",
  "confidence": 0.0-1.0,
  "reasoning": "Detailed English reasoning. Mention: positions, key evidence, why now, what could invalidate.",
  "valid_for_minutes": 15,
  "signals": [
    {{
      "signal_type": "ENTRY|EXIT",
      "action": "BUY|SELL|CLOSE_LONG|CLOSE_SHORT|SCALE_IN|SCALE_OUT|REVERSE",
      "execution_mode": "CONDITIONAL|IMMEDIATE",
      "position_size": 0.1-5.0,
      "confidence": 0.0-1.0,
      "entry_price": number|null,
      "stop_loss": number|null,
      "take_profit": number|null,
      "conditions": [
        {{"indicator":"current_price|rsi_14|macd|...","operator":">|<|>=|<=|crosses_above|crosses_below","threshold": number}}
      ],
      "rationale": "Short English rationale for this signal"
    }}
  ]
}}
"""

        return prompt

    def _parse_llm_response(
        self,
        llm_response: Any,
        aggregated: Dict[str, Any],
        agent_results: list[AnalysisResult],
        position_data: Dict[str, Any],
    ) -> AnalysisResult:
        """Parse LLM judge response into AnalysisResult.

        Stores the raw judge payload in details["judge"] and exposes structured signals in details["signals"].
        """
        try:
            # Extract content from LLM response
            if hasattr(llm_response, 'content'):
                content = llm_response.content
            elif hasattr(llm_response, 'text'):
                content = llm_response.text
            elif isinstance(llm_response, str):
                content = llm_response
            else:
                content = str(llm_response)

            # Try to parse JSON
            import json
            parsed = json.loads(content)

            # Backward compat keys
            final_decision = parsed.get("decision") or parsed.get("final_decision") or "HOLD"
            final_decision = str(final_decision).upper()
            if final_decision not in {"BUY", "SELL", "HOLD", "CLOSE_LONG", "CLOSE_SHORT", "SCALE_IN", "SCALE_OUT", "REVERSE"}:
                final_decision = "HOLD"

            # For compatibility with downstream logic, keep decision in BUY/SELL/HOLD family
            decision_for_engine = final_decision
            if final_decision in {"CLOSE_LONG", "SCALE_OUT"}:
                decision_for_engine = "SELL"
            elif final_decision in {"CLOSE_SHORT"}:
                decision_for_engine = "BUY"
            elif final_decision in {"REVERSE"}:
                # Reverse is ambiguous without side; keep HOLD and rely on signals
                decision_for_engine = "HOLD"

            signals = parsed.get("signals") if isinstance(parsed.get("signals"), list) else None

            # Build agent breakdown for UI compatibility
            agent_breakdown = {
                "buy_signals": sum(1 for r in agent_results if getattr(r, 'decision', '').upper() == 'BUY'),
                "sell_signals": sum(1 for r in agent_results if getattr(r, 'decision', '').upper() == 'SELL'),
                "hold_signals": sum(1 for r in agent_results if getattr(r, 'decision', '').upper() in ['HOLD', '']),
                "total_agents": len(agent_results)
            }

            # Create aggregated analysis for UI compatibility
            aggregated_analysis = {
                "consensus_direction": decision_for_engine,
                "confidence_score": float(parsed.get("confidence", 0.0)),
                "agent_breakdown": agent_breakdown,
                "key_insights": [parsed.get("reasoning", "Judge decision generated")],
                "signal_strength": float(parsed.get("confidence", 0.0))
            }

            return AnalysisResult(
                decision=decision_for_engine,
                confidence=float(parsed.get("confidence", 0.0)),
                details={
                    "reasoning": parsed.get("reasoning", ""),
                    "valid_for_minutes": parsed.get("valid_for_minutes", 15),
                    "signals": signals or [],
                    "llm_generated": True,
                    "aggregated_analysis": aggregated_analysis,
                    "judge": parsed,
                    "positions": position_data.get("positions") if isinstance(position_data, dict) else [],
                    "agent_snapshot": [
                        {
                            "agent": getattr(r, "agent", None) or "UnknownAgent",
                            "decision": getattr(r, "decision", "HOLD"),
                            "confidence": float(getattr(r, "confidence", 0.0) or 0.0),
                        }
                        for r in agent_results
                    ],
                }
            )

        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return self._generate_fallback_decision(aggregated, True)

    async def _create_signals_from_decision(
        self,
        decision: AnalysisResult,
        instrument: str,
        current_price: Optional[float] = None,
        technical_indicators: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create TradingCondition signals from orchestrator decision.
        
        This method creates conditional signals that can be monitored in real-time
        and executed when conditions are met.
        
        Args:
            decision: AnalysisResult from orchestrator
            instrument: Trading instrument
            current_price: Current market price
            technical_indicators: Current technical indicator values
        """
        try:
            from .signal_creator import create_signals_from_decision, save_signal_to_mongodb
            
            # Determine current_price if not provided: prefer latest tick
            cp = current_price
            if cp is None:
                try:
                    if hasattr(self.market_data_provider, 'get_latest_ticks'):
                        ticks = await self.market_data_provider.get_latest_ticks(instrument, limit=1)
                        if ticks:
                            t = ticks[0]
                            if isinstance(t, dict):
                                cp = t.get('last_price') or t.get('last') or t.get('price')
                            else:
                                cp = getattr(t, 'last_price', None) or getattr(t, 'price', None) or getattr(t, 'last', None)
                except Exception:
                    cp = None

            # Create signals from decision (prefer fetched current_price)
            signals = create_signals_from_decision(
                analysis_result=decision,
                instrument=instrument,
                technical_indicators=technical_indicators,
                current_price=cp,
                strategy_config=self.config.get("strategy_config")
            )
            
            if not signals:
                logger.debug(f"No signals created from decision {decision.decision}")
                return
            
            logger.info(f"Created {len(signals)} signal(s) from decision {decision.decision}")
            
            # Save signals to MongoDB if available
            # PyMongo Database objects don't support truthiness testing in newer versions.
            # We avoid any comparison operations and just try to use mongo_db directly.
            mongo_db = getattr(self, 'mongo_db', None)
            
            # Try to use mongo_db without any None comparison to avoid NotImplementedError
            # We'll catch any errors if mongo_db is None or invalid
            try:
                # Verify mongo_db is usable by attempting to access a safe attribute
                # If this fails, mongo_db is likely None or invalid
                _ = mongo_db.name  # Database objects have a 'name' attribute
                # If we get here, mongo_db is valid - proceed with saving
                for signal in signals:
                    try:
                        inserted_id = await save_signal_to_mongodb(signal, mongo_db)
                        logger.info(f"Saved signal {signal.condition_id} to MongoDB with id {inserted_id}")

                        # If decision included detailed options_strategy, attach it to the saved signal document
                        try:
                            if decision and getattr(decision, 'options_strategy', None):
                                from bson import ObjectId
                                collection = mongo_db['signals']
                                options_summary = decision.details.get('options_strategy') if decision.details else None
                                if options_summary:
                                    collection.update_one({'_id': ObjectId(inserted_id)}, {'$set': {'metadata.options_strategy': options_summary}})
                        except Exception as attach_err:
                            logger.debug(f"Failed to attach options_strategy to signal doc: {attach_err}")

                    except Exception as save_error:
                        logger.error(f"Failed to save signal {signal.condition_id} to MongoDB: {save_error}")
            except (NotImplementedError, AttributeError, TypeError):
                # mongo_db is None, doesn't support comparison, or is invalid - skip save
                pass
            
            # Add signals to SignalMonitor if available
            if self.signal_monitor:
                for signal in signals:
                    try:
                        self.signal_monitor.add_signal(signal)
                        logger.info(f"Added signal {signal.condition_id} to SignalMonitor")
                    except Exception as monitor_error:
                        logger.error(f"Failed to add signal {signal.condition_id} to SignalMonitor: {monitor_error}")
            
            # Update decision details with created signals
            if decision.details:
                decision.details["signals_created"] = len(signals)
                decision.details["signal_ids"] = [s.condition_id for s in signals]
            
        except ImportError as import_error:
            logger.warning(f"Signal creator module not available: {import_error}")
        except Exception as e:
            logger.error(f"Error creating signals from decision: {e}", exc_info=True)
            raise

    def _generate_fallback_decision(self, aggregated: Dict[str, Any], market_hours: bool, agent_results: list = None, failed_agents: list = None) -> AnalysisResult:
        """Generate fallback decision when LLM is unavailable."""
        logger.info(f"DEBUG: _generate_fallback_decision called with {len(agent_results) if agent_results else 0} agent results")
        direction = aggregated.get('consensus_direction', 'HOLD')
        strength = aggregated.get('signal_strength', 0.0)
        risk = aggregated.get('risk_assessment', 'UNKNOWN')

        # Conservative fallback logic
        # In BACKTEST mode, ignore market hours (always consider market open)
        execution_mode = self.config.get('execution_mode', 'LIVE')
        effective_market_hours = market_hours if execution_mode != 'BACKTEST' else True

        if not effective_market_hours:
            decision = "HOLD"
            confidence = 0.1
            reasoning = "Market closed - no trading"
        elif risk == "HIGH" or strength < 0.4:
            decision = "HOLD"
            confidence = 0.3
            reasoning = f"Conservative approach - risk: {risk}, strength: {strength:.1%}"
        else:
            decision = direction
            confidence = min(strength * 0.8, 0.6)  # Conservative confidence
            reasoning = f"Consensus {direction} with {strength:.1%} strength"

        # Create agent snapshot from real agent results if available
        agent_snapshot = []
        failed_agents = failed_agents or []

        if agent_results:
            # Use real agent results for detailed analysis
            for result in agent_results:
                agent_name = getattr(result, 'agent', None) or getattr(result, '_agent_name', 'Unknown')
                agent_snapshot.append({
                    "agent": agent_name,
                    "decision": result.decision or 'HOLD',
                    "confidence": float(result.confidence) if result.confidence is not None else 0.0,
                    "timestamp": getattr(result, 'timestamp', None),
                    "details": result.details or {}  # Preserve full agent details
                })

            # Add failed agents with error information
            for failed_agent in failed_agents:
                agent_snapshot.append({
                    "agent": failed_agent["agent"],
                    "decision": "ERROR",
                    "confidence": 0.0,
                    "timestamp": None,
                    "details": {
                        "error": failed_agent["error"],
                        "error_type": failed_agent["error_type"],
                        "failed": True,
                        "reasoning": f"Agent failed with {failed_agent['error_type']}: {failed_agent['error'][:100]}..."
                    }
                })

            logger.info(f"Created agent snapshot: {len(agent_results)} successful, {len(failed_agents)} failed")
        else:
            # No agent results available - this is a critical failure
            logger.error("❌ CRITICAL: No agent results available for fallback decision")
            reasoning = "CRITICAL FAILURE: All agents failed or no agents configured. Unable to perform analysis."

            # Create error entries for all expected agents
            for agent in self.agents:
                agent_name = getattr(agent, '_agent_name', agent.__class__.__name__)
                agent_snapshot.append({
                    "agent": agent_name,
                    "decision": "ERROR",
                    "confidence": 0.0,
                    "timestamp": None,
                    "details": {
                        "error": "Agent execution failed - no results available",
                        "error_type": "CriticalFailure",
                        "failed": True,
                        "reasoning": reasoning
                    }
                })

            # Force HOLD decision with very low confidence
            decision = "HOLD"
            confidence = 0.0
            reasoning = "CRITICAL: All agents failed. Defaulting to HOLD with zero confidence."

        # Enhance decision with trading parameters
        enhanced_details = self._enhance_decision_with_trading_params(
            decision, confidence, aggregated, agent_results
        )

        return AnalysisResult(
            decision=decision,
            confidence=confidence,
            details={
                "reasoning": reasoning,
                "fallback_mode": True,
                "aggregated_analysis": aggregated,
                "market_hours": market_hours,
                "risk_adjusted": True,
                "agent_snapshot": agent_snapshot,
                **enhanced_details  # Add trading parameters
            }
        )

    async def _save_agent_decisions_to_api(self, agent_results: list[AnalysisResult], instrument: str):
        """Save individual agent decisions to API service for UI display and Redis publishing."""
        try:
            import aiohttp
            import json
            from datetime import datetime

            # Prepare agent decisions for API
            decisions_data = []
            for result in agent_results:
                agent_name = getattr(result, 'agent', None) or getattr(result, '_agent_name', 'Unknown')

                # Map decision to UI-friendly format
                decision = result.decision
                if decision and 'BUY' in str(decision).upper():
                    direction = 'BUY'
                elif decision and 'SELL' in str(decision).upper():
                    direction = 'SELL'
                else:
                    direction = 'HOLD'

                decisions_data.append({
                    "agent_name": agent_name,
                    "signal": str(result.decision) if result.decision else "HOLD",
                    "decision": str(result.decision) if result.decision else "HOLD",
                    "direction": direction,
                    "confidence": float(result.confidence) if result.confidence is not None else 0.0,
                    "timestamp": datetime.now().isoformat(),
                    "instrument": instrument
                })

            if not decisions_data:
                logger.warning("No agent decisions to save")
                return

            # Send to API service
            api_url = "http://localhost:8004/api/v1/decisions"
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=decisions_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        saved_count = result.get('saved_count', 0)
                        logger.info(f"[OK] Saved {saved_count} agent decisions to API service")
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to save agent decisions: HTTP {response.status} - {error_text}")

        except ImportError as ie:
            logger.warning(f"aiohttp not available for API calls: {ie}")
        except Exception as e:
            logger.error(f"Failed to save agent decisions to API: {e}", exc_info=True)

    async def _publish_agent_analysis_results(self, agent_results: list[AnalysisResult], instrument: str, context: Dict[str, Any]):
        """Publish agent analysis results to Redis for real-time dashboard updates."""
        logger.info(f"Publishing {len(agent_results)} agent analysis results to Redis")
        print(f"DEBUG: Publishing agent results for {len(agent_results)} agents")
        try:
            import redis.asyncio as redis_async
            import json
            import os
            from datetime import datetime

            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))

            redis_client = redis_async.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

            for result in agent_results:
                try:
                    agent_name = getattr(result, 'agent', None) or getattr(result, '_agent_name', 'Unknown')
                    print(f"DEBUG: Publishing agent {agent_name}: {result.decision} ({result.confidence})")

                    # Build agent data payload
                    # Ensure details is a dict
                    details = result.details if isinstance(result.details, dict) else {}

                    agent_data = {
                        'type': 'agent_analysis',
                        'timestamp': datetime.now().isoformat(),
                        'agent_name': agent_name,
                        'instrument': instrument,
                        'decision': result.decision or 'HOLD',
                        'confidence': float(result.confidence) if result.confidence is not None else 0.0,
                        'details': details,
                        'cycle_info': context.get('cycle_info', {}),
                        'seq': context.get('cycle_info', {}).get('cycle_number', 0)
                    }

                    # Add technical indicators if available
                    if details and 'indicators' in details:
                        agent_data['technical_indicators'] = details['indicators']

                    # Add reasoning if available
                    if details and 'reasoning' in details:
                        agent_data['reasoning'] = details['reasoning']

                    # Convert numpy types to Python types for JSON serialization
                    def convert_numpy_types(obj):
                        if hasattr(obj, 'item'):  # numpy scalar
                            return obj.item()
                        elif isinstance(obj, dict):
                            return {k: convert_numpy_types(v) for k, v in obj.items()}
                        elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
                            return [convert_numpy_types(item) for item in obj]
                        else:
                            return obj

                    agent_data = convert_numpy_types(agent_data)

                    # Debug: Log what we're publishing
                    logger.debug(f"Publishing agent analysis for {agent_name}: decision={result.decision}, confidence={result.confidence:.2f}")

                    # Publish to Redis pub/sub channels (use decision channels for real-time agent updates)
                    channel = f"engine:decision:{agent_name}"
                    await redis_client.publish(channel, json.dumps(agent_data))

                    # Also publish to general decision channel
                    await redis_client.publish("engine:decision", json.dumps(agent_data))

                    logger.debug(f"Published agent analysis for {agent_name}: {result.decision} ({result.confidence:.2f})")

                except Exception as agent_err:
                    logger.warning(f"Failed to publish agent {agent_name} analysis: {agent_err}")

            await redis_client.aclose()

        except ImportError:
            logger.debug("redis.asyncio not available for publishing")
        except Exception as e:
            logger.error(f"Error publishing agent analysis results: {e}", exc_info=True)

    async def _save_agent_decisions_to_mongodb(self, agent_results: list[AnalysisResult], instrument: str, context: Dict[str, Any]):
        """Save detailed agent analysis results to MongoDB for dashboard retrieval."""
        logger.info(f"Saving {len(agent_results)} agent decisions to MongoDB")

        try:
            from datetime import datetime
            import os

            # Get MongoDB client
            if self.mongo_db is not None:
                db = self.mongo_db
            else:
                # Fallback: create mongo client
                from core_kernel.src.core_kernel.mongodb_schema import get_mongo_client
                mongo_client = get_mongo_client()
                db = mongo_client["zerodha_trading"]
            agent_discussions = db["agent_discussions"]

            timestamp = datetime.now()
            saved_count = 0

            for result in agent_results:
                try:
                    agent_name = getattr(result, 'agent', None) or getattr(result, '_agent_name', 'Unknown')
                    signal = result.decision or 'HOLD'
                    confidence = float(result.confidence) if result.confidence is not None else 0.0

                    # Get reasoning from details
                    details = result.details or {}
                    reasoning = details.get('reasoning') or details.get('thesis') or 'Decision made'

                    # Get system context for run isolation
                    from .system_context import get_system_context
                    system_context = get_system_context()

                    discussion_doc = {
                        "timestamp": timestamp.isoformat(),
                        "agent_name": agent_name,
                        "signal": signal,
                        "decision": signal,  # Alias for compatibility
                        "confidence": confidence,
                        "reasoning": reasoning,
                        "indicators": details.get('indicators') or details.get('technical_signals') or {},
                        "instrument": instrument,
                        "details": details,  # Store full details for dashboard
                        **system_context.get_metadata()  # Add run isolation metadata
                    }

                    agent_discussions.insert_one(discussion_doc)
                    saved_count += 1
                    logger.debug(f"Saved agent decision for {agent_name}: {signal} ({confidence})")

                except Exception as agent_err:
                    logger.warning(f"Failed to save agent decision: {agent_err}")

            logger.info(f"Successfully saved {saved_count} agent decisions to MongoDB")

        except Exception as e:
            logger.error(f"Error saving agent decisions to MongoDB: {e}", exc_info=True)
            raise

    async def _publish_orchestrator_decision(self, final_decision: AnalysisResult, agent_results: list[AnalysisResult], instrument: str, context: Dict[str, Any]):
        """Publish orchestrator decision to Redis for real-time dashboard updates."""
        print(f"DEBUG: _publish_orchestrator_decision called for {instrument}: {final_decision.decision}")
        logger.info(f"Publishing orchestrator decision: {final_decision.decision} with {len(agent_results)} agent results")
        print(f"DEBUG: Publishing to channels: engine:orchestrator_decision and engine:orchestrator_decision:{instrument}")
        try:
            import redis
            import json
            import os
            from datetime import datetime

            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))

            redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

            # Build orchestrator decision payload
            orchestrator_data = {
                'type': 'orchestrator_decision',
                'timestamp': datetime.now().isoformat(),
                'instrument': instrument,
                'final_decision': final_decision.decision or 'HOLD',
                'confidence': float(final_decision.confidence) if final_decision.confidence is not None else 0.0,
                'reasoning': final_decision.details.get('reasoning', '') if final_decision.details else '',
                'agent_responses': [],
                'signal_created': final_decision.decision not in ["HOLD", "ERROR"] or any(strategy in final_decision.decision.upper() for strategy in ["IRON_CONDOR", "BUY_CALL", "BUY_PUT", "BEAR_CALL", "BULL_PUT"]),
                'cycle_info': context.get('cycle_info', {}),
                'seq': context.get('cycle_info', {}).get('cycle_number', 0)
            }

            # Add agent breakdown - prefer judge's agent_snapshot if available (for LLM decisions)
            agent_responses = []

            # Check if this is a judge-generated decision with agent_snapshot
            if (final_decision.details and
                final_decision.details.get('llm_generated') and
                'agent_snapshot' in final_decision.details):

                # Use judge's agent snapshot (includes all agents even if some failed)
                for agent_info in final_decision.details['agent_snapshot']:
                    agent_responses.append({
                        'agent': agent_info.get('agent', 'Unknown'),
                        'decision': agent_info.get('decision', 'HOLD'),
                        'confidence': float(agent_info.get('confidence', 0.0)),
                        'details': agent_info.get('reasoning', '')  # Judge may not have this
                    })
            else:
                # Fallback to original agent_results for non-judge decisions
                for result in agent_results:
                    agent_name = getattr(result, 'agent', None) or getattr(result, '_agent_name', 'Unknown')
                    agent_response = {
                        'agent': agent_name,
                        'decision': result.decision or 'HOLD',
                        'confidence': float(result.confidence) if result.confidence is not None else 0.0,
                        'details': result.details or {}  # Preserve full details, not just reasoning
                    }
                    agent_responses.append(agent_response)

            orchestrator_data['agent_responses'] = agent_responses

            # Add aggregated analysis for UI compatibility
            if final_decision.details and 'aggregated_analysis' in final_decision.details:
                agg = final_decision.details['aggregated_analysis']
                orchestrator_data['aggregated_analysis'] = agg
                if 'key_insights' in agg:
                    orchestrator_data['key_insights'] = agg['key_insights']
                if 'agent_breakdown' in agg:
                    orchestrator_data['agent_breakdown'] = agg['agent_breakdown']

            # Convert numpy types to Python types for JSON serialization
            def convert_numpy_types(obj):
                if hasattr(obj, 'item'):  # numpy scalar
                    return obj.item()
                elif isinstance(obj, dict):
                    return {k: convert_numpy_types(v) for k, v in obj.items()}
                elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
                    return [convert_numpy_types(item) for item in obj]
                else:
                    return obj

            print(f"DEBUG: orchestrator_data before numpy conversion: {type(orchestrator_data)} keys: {list(orchestrator_data.keys()) if isinstance(orchestrator_data, dict) else 'not dict'}")
            orchestrator_data = convert_numpy_types(orchestrator_data)
            print(f"DEBUG: orchestrator_data after numpy conversion: {type(orchestrator_data)}")

            # Publish to Redis pub/sub channels (use orchestrator prefix to distinguish from agent decisions)
            print(f"DEBUG: Publishing to Redis channels...")
            json_str = json.dumps(orchestrator_data)
            print(f"DEBUG: JSON string length: {len(json_str)} preview: {json_str[:100]}...")
            result1 = redis_client.publish("engine:orchestrator_decision", json_str)
            result2 = redis_client.publish(f"engine:orchestrator_decision:{instrument}", json_str)
            print(f"DEBUG: Publish results - general: {result1}, specific: {result2}")

            # Persist last decision in Redis for "replay on subscribe"
            # Publish to Redis with run isolation
            from .system_context import get_cache_manager
            cache_manager = get_cache_manager()
            cache_manager.set(f"engine:orchestrator_decision:{instrument}:latest", json.dumps(orchestrator_data), expire_seconds=3600)  # 1 hour
            cache_manager.set("engine:orchestrator_decision:latest", json.dumps(orchestrator_data), expire_seconds=3600)
            print(f"DEBUG: Set Redis keys for latest decisions")

            logger.info(f"Published orchestrator decision: {final_decision.decision} ({final_decision.confidence:.2f}) for {instrument}")

            redis_client.close()
            print(f"DEBUG: Redis client closed")

        except ImportError:
            logger.debug("redis.asyncio not available for publishing")
        except Exception as e:
            logger.error(f"Error publishing orchestrator decision: {e}", exc_info=True)

    def _enhance_decision_with_trading_params(
        self,
        decision: str,
        confidence: float,
        aggregated: Dict[str, Any],
        agent_results: list = None
    ) -> Dict[str, Any]:
        """Enhance decision with position sizing, stop loss, and profit targets."""

        # Base trading parameters
        trading_params = {
            "position_sizing": {},
            "risk_management": {},
            "profit_targets": {},
            "execution_strategy": {}
        }

        # Only calculate for actual trade decisions
        if decision in ["BUY", "SELL"]:
            # Get current price for calculations
            current_price = aggregated.get("current_price", 0)
            if not current_price:
                # Try to get from market data
                market_data = aggregated.get("market_data", {})
                current_price = market_data.get("current_price") or market_data.get("last_price", 0)

            # Calculate position sizing based on confidence and risk
            position_size = self._calculate_position_size(confidence, current_price)

            # Calculate stop loss and profit targets
            stop_loss, profit_targets = self._calculate_risk_targets(
                decision, current_price, confidence
            )

            trading_params.update({
                "position_sizing": position_size,
                "risk_management": {
                    "stop_loss_price": stop_loss,
                    "stop_loss_percentage": abs(stop_loss - current_price) / current_price * 100 if current_price else 0,
                    "max_loss_per_trade": 0.02,  # 2% max loss per trade
                    "portfolio_risk_limit": 0.05   # 5% max portfolio risk
                },
                "profit_targets": profit_targets,
                "execution_strategy": {
                    "entry_type": "MARKET",  # MARKET or LIMIT
                    "time_in_force": "DAY",   # DAY, GTC, IOC
                    "partial_fills_allowed": True,
                    "scale_orders": position_size.get("scale_orders", False)
                }
            })

        return trading_params

    def _calculate_position_size(self, confidence: float, current_price: float) -> Dict[str, Any]:
        """Calculate optimal position size based on confidence and risk."""

        # Base position sizes (adjust based on confidence)
        confidence_multiplier = {
            0.0: 0.0,   # No position for 0 confidence
            0.3: 0.3,   # Small position for low confidence
            0.5: 0.6,   # Medium position for medium confidence
            0.7: 0.9,   # Large position for high confidence
            1.0: 1.0    # Full position for maximum confidence
        }

        # Find appropriate multiplier
        multiplier = 0.0
        for conf_threshold, mult in confidence_multiplier.items():
            if confidence >= conf_threshold:
                multiplier = mult
            else:
                break

        # Calculate actual position size
        base_position_size = 100000  # Base 1 lakh rupees
        position_value = base_position_size * multiplier

        if current_price > 0:
            quantity = int(position_value / current_price)
        else:
            quantity = 0

        return {
            "position_value": position_value,
            "quantity": quantity,
            "confidence_multiplier": multiplier,
            "scale_orders": multiplier > 0.7,  # Use scale orders for large positions
            "max_single_order_value": 50000,   # Max 50k per order
            "order_count": max(1, min(3, int(multiplier * 3)))  # 1-3 orders based on confidence
        }

    def _calculate_risk_targets(
        self,
        decision: str,
        current_price: float,
        confidence: float
    ) -> tuple[float, Dict[str, Any]]:
        """Calculate stop loss and profit targets."""

        if current_price <= 0:
            return current_price, {"targets": []}

        # Base stop loss percentages (tighter stops for higher confidence)
        stop_loss_pct = {
            0.3: 0.03,   # 3% stop for low confidence
            0.5: 0.025,  # 2.5% stop for medium confidence
            0.7: 0.02,   # 2% stop for high confidence
            1.0: 0.015   # 1.5% stop for max confidence
        }

        # Find appropriate stop loss percentage
        stop_pct = 0.03  # Default
        for conf_threshold, pct in stop_loss_pct.items():
            if confidence >= conf_threshold:
                stop_pct = pct

        # Calculate stop loss price
        if decision == "BUY":
            stop_loss = current_price * (1 - stop_pct)
            # Profit targets: 2:1, 3:1, 5:1 risk-reward ratios
            targets = [
                {"price": current_price * (1 + stop_pct * 2), "ratio": "2:1"},
                {"price": current_price * (1 + stop_pct * 3), "ratio": "3:1"},
                {"price": current_price * (1 + stop_pct * 5), "ratio": "5:1"}
            ]
        else:  # SELL
            stop_loss = current_price * (1 + stop_pct)
            # Profit targets for short positions
            targets = [
                {"price": current_price * (1 - stop_pct * 2), "ratio": "2:1"},
                {"price": current_price * (1 - stop_pct * 3), "ratio": "3:1"},
                {"price": current_price * (1 - stop_pct * 5), "ratio": "5:1"}
            ]

        profit_targets = {
            "targets": targets,
            "trailing_stop": confidence > 0.7,  # Use trailing stops for high confidence
            "trailing_stop_distance": stop_pct * current_price,
            "scale_out_levels": [0.33, 0.67, 1.0] if confidence > 0.5 else [0.5, 1.0]  # Scale out at these levels
        }

        return round(stop_loss, 2), profit_targets

    def _apply_portfolio_risk_controls(
        self,
        decision: AnalysisResult,
        instrument: str,
        position_data: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> AnalysisResult:
        """Apply portfolio-level risk controls to the trading decision."""

        # Skip risk controls for HOLD decisions
        if decision.decision == "HOLD":
            return decision

        # Extract position information
        positions = position_data.get("positions", [])
        portfolio_summary = position_data.get("portfolio_summary", {})

        # Calculate current portfolio risk metrics
        portfolio_risk = self._calculate_portfolio_risk_metrics(
            positions, portfolio_summary, market_data
        )

        # Check if proposed trade violates risk limits
        risk_violation = self._check_risk_limits(
            decision, instrument, portfolio_risk, market_data
        )

        if risk_violation:
            logger.warning(f"🚫 Risk violation detected: {risk_violation['reason']}")

            # Create modified decision
            modified_decision = AnalysisResult(
                decision="HOLD",
                confidence=max(0.1, decision.confidence * 0.3),  # Reduce confidence significantly
                details={
                    **decision.details,
                    "risk_override": True,
                    "risk_violation": risk_violation,
                    "original_decision": decision.decision,
                    "portfolio_risk": portfolio_risk,
                    "reasoning": f"RISK OVERRIDE: {risk_violation['reason']}. Original decision was {decision.decision} but rejected due to portfolio risk limits."
                }
            )
            return modified_decision

        # No risk violation - return original decision with risk metrics added
        decision.details["portfolio_risk"] = portfolio_risk
        decision.details["risk_assessment"] = "PASSED"
        return decision

    def _calculate_portfolio_risk_metrics(
        self,
        positions: List[Dict[str, Any]],
        portfolio_summary: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate comprehensive portfolio risk metrics."""

        # Get current portfolio value
        portfolio_value = portfolio_summary.get("total_value", 1000000)  # Default 10 lakhs
        cash_available = portfolio_summary.get("cash_available", portfolio_value * 0.1)

        # Calculate position concentrations
        position_values = []
        sector_exposure = {}
        instrument_exposure = {}

        for position in positions:
            if isinstance(position, dict) and position.get("quantity", 0) != 0:
                instrument = position.get("instrument", "UNKNOWN")
                quantity = abs(position.get("quantity", 0))
                avg_price = position.get("average_price", 0)
                current_price = market_data.get("current_price", avg_price)

                position_value = quantity * current_price
                position_values.append(position_value)

                # Track instrument exposure
                instrument_exposure[instrument] = instrument_exposure.get(instrument, 0) + position_value

                # Simplified sector mapping (would be more sophisticated in real system)
                sector = self._map_instrument_to_sector(instrument)
                sector_exposure[sector] = sector_exposure.get(sector, 0) + position_value

        # Calculate risk metrics
        total_position_value = sum(position_values)
        position_concentration = total_position_value / portfolio_value if portfolio_value > 0 else 0

        # Largest position as % of portfolio
        max_position_pct = max(position_values) / portfolio_value if position_values else 0

        # Sector concentration (largest sector)
        max_sector_pct = max(sector_exposure.values()) / portfolio_value if sector_exposure else 0

        return {
            "portfolio_value": portfolio_value,
            "cash_available": cash_available,
            "total_positions_value": total_position_value,
            "position_concentration": position_concentration,
            "max_position_pct": max_position_pct,
            "max_sector_pct": max_sector_pct,
            "active_positions": len([p for p in positions if abs(p.get("quantity", 0)) > 0]),
            "sector_diversity": len(sector_exposure),
            "instrument_diversity": len(instrument_exposure)
        }

    def _check_risk_limits(
        self,
        decision: AnalysisResult,
        instrument: str,
        portfolio_risk: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """Check if proposed trade violates portfolio risk limits."""

        # Extract trading parameters from decision
        trading_params = decision.details.get("position_sizing", {})
        position_value = trading_params.get("position_value", 0)
        portfolio_value = portfolio_risk.get("portfolio_value", 1000000)

        # Risk limits
        MAX_PORTFOLIO_RISK = 0.05  # 5% max portfolio risk per trade
        MAX_POSITION_SIZE = 0.10   # 10% max position size
        MAX_SECTOR_EXPOSURE = 0.25 # 25% max sector exposure
        MIN_CASH_RESERVE = 0.05   # 5% minimum cash reserve

        # Check position size limit
        position_pct = position_value / portfolio_value
        if position_pct > MAX_POSITION_SIZE:
            return {
                "type": "position_size",
                "reason": f"Position size {position_pct:.1%} exceeds limit of {MAX_POSITION_SIZE:.1%}",
                "limit": MAX_POSITION_SIZE,
                "actual": position_pct
            }

        # Check portfolio concentration limit
        if portfolio_risk["position_concentration"] + position_pct > MAX_PORTFOLIO_RISK:
            return {
                "type": "portfolio_concentration",
                "reason": f"Total portfolio risk would be {portfolio_risk['position_concentration'] + position_pct:.1%}, exceeding {MAX_PORTFOLIO_RISK:.1%} limit",
                "limit": MAX_PORTFOLIO_RISK,
                "actual": portfolio_risk["position_concentration"] + position_pct
            }

        # Check cash reserve requirement
        cash_available = portfolio_risk.get("cash_available", 0)
        if cash_available < position_value:
            return {
                "type": "insufficient_cash",
                "reason": f"Insufficient cash: available {cash_available:,.0f}, required {position_value:,.0f}",
                "available": cash_available,
                "required": position_value
            }

        # Check sector concentration (simplified - would need proper sector mapping)
        sector = self._map_instrument_to_sector(instrument)
        current_sector_exposure = portfolio_risk.get("max_sector_pct", 0)
        if current_sector_exposure > MAX_SECTOR_EXPOSURE:
            return {
                "type": "sector_concentration",
                "reason": f"Sector exposure {current_sector_exposure:.1%} exceeds {MAX_SECTOR_EXPOSURE:.1%} limit",
                "limit": MAX_SECTOR_EXPOSURE,
                "actual": current_sector_exposure
            }

        # All checks passed
        return None

    def _map_instrument_to_sector(self, instrument: str) -> str:
        """Map instrument to sector for risk management."""
        instrument = instrument.upper()

        # Simplified sector mapping
        sector_map = {
            "NIFTY": "INDEX",
            "BANKNIFTY": "BANKING",
            "RELIANCE": "ENERGY",
            "TCS": "IT",
            "INFY": "IT",
            "HDFC": "FINANCIAL",
            "ICICI": "FINANCIAL",
            "BAJAJ": "AUTOMOTIVE",
            "MARUTI": "AUTOMOTIVE"
        }

        # Check for exact matches first
        if instrument in sector_map:
            return sector_map[instrument]

        # Check for partial matches (e.g., BANKNIFTY26JANFUT -> BANKNIFTY -> BANKING)
        for key, sector in sector_map.items():
            if key in instrument:
                return sector

        return "UNKNOWN"
