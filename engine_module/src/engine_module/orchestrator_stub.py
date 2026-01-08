"""Orchestrator stub implementation for trading engine.

This module provides a skeleton TradingOrchestrator that demonstrates
dependency injection and async execution flow. Implementation details
are left as TODOs for incremental development.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional, Protocol, runtime_checkable
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
        position_manager: Optional[PositionManager] = None,
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
            **kwargs: Additional config (e.g., instruments, lookback_days)
        """
        self.llm_client = llm_client
        self.market_data_provider = market_data_provider
        self.options_data_provider = options_data_provider
        self.agents = agents or []
        self.news_service = news_service
        self.technical_data_provider = technical_data_provider
        self.position_manager = position_manager
        self.config = kwargs

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
        instrument = context.get("instrument", "BANKNIFTY")
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
        cycle_interval = context.get("cycle_interval", "15min")

        logger.info(f"Starting {cycle_interval} analysis cycle for {instrument} at {timestamp}")

        try:
            # Step 1: Fetch market data (15min OHLC + recent ticks)
            market_data = await self._fetch_market_data(instrument)

            # Step 2: Fetch options chain data
            options_chain = await self._fetch_options_data(instrument)

            # Step 3: Fetch news data (if news service available)
            news_data = await self._fetch_news_data(instrument)

            # Step 3.5: Fetch technical indicators (if technical data provider available)
            technical_data = await self._fetch_technical_data(instrument)

            # Step 3.6: Fetch position data (if position manager available)
            position_data = await self._fetch_position_data(instrument)

            # Step 4: Run all agents in parallel
            agent_results = await self._run_agents_parallel(market_data, options_chain, news_data, technical_data, position_data, context)

            # Step 4: Aggregate agent signals
            aggregated_analysis = self._aggregate_results(agent_results)

            # Step 5: Generate LLM-powered trading decision
            if not self.agents:
                # Stub behavior when no agents configured (for backward compatibility)
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
            elif market_hours and self.llm_client:
                final_decision = await self._generate_llm_decision(aggregated_analysis, context)
            else:
                final_decision = self._generate_fallback_decision(aggregated_analysis, market_hours)

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

            # Step 6: Execute trading decision if position manager available
            if self.position_manager and final_decision.decision != "HOLD":
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

    async def _fetch_market_data(self, instrument: str) -> Dict[str, Any]:
        """Fetch comprehensive market data for analysis."""
        try:
            # Use the market_data_provider if available
            if self.market_data_provider and hasattr(self.market_data_provider, 'get_ohlc_data'):
                # New Redis-based provider
                ohlc_data = await self.market_data_provider.get_ohlc_data(instrument, periods=100)
                current_price = ohlc_data[-1].get('close', 0) if ohlc_data else 0
                return {
                    "instrument": instrument,
                    "ticks": [],  # Not available from Redis provider
                    "ohlc": ohlc_data,
                    "current_price": current_price,
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
            technical_indicators = await self.technical_data_provider.get_technical_indicators(instrument, periods=100)

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
                                 position_data: Dict[str, Any],
                                 context: Dict[str, Any]) -> list[AnalysisResult]:
        """Run all agents in parallel and collect their results."""
        if not self.agents:
            logger.warning("No agents configured for orchestrator")
            return []

        # Prepare context for agents
        agent_context = {
            **context,
            **market_data,
            **options_data,
            **news_data,
            **technical_data,
            **position_data,
            "options_chain": options_data,  # Alias for backward compatibility
            "market_data": market_data,      # Alias for backward compatibility
            "news_data": news_data,          # Alias for backward compatibility
            "technical_data": technical_data, # Alias for backward compatibility
            "position_data": position_data   # Alias for backward compatibility
        }

        # Run all agents concurrently
        tasks = [agent.analyze(agent_context) for agent in self.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log errors
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                agent_name = getattr(self.agents[i], '__class__', {}).get('__name__', f'Agent_{i}')
                logger.error(f"Agent {agent_name} failed: {result}")
            else:
                valid_results.append(result)

        logger.info(f"Successfully ran {len(valid_results)}/{len(self.agents)} agents")
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
            'risk': 2.0,           # Risk agent gets veto power
            'execution': 0.0       # Execution doesn't vote, only validates
        }

        # Initialize weighted aggregation
        buy_signals = 0  # Count
        sell_signals = 0
        hold_signals = 0
        buy_weight = 0.0  # Weighted score
        sell_weight = 0.0
        hold_weight = 0.0
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
            agent_name = getattr(result, '_agent_name', 'Unknown')
            details = result.details or {}
            
            # Determine agent weight based on category
            weight = 1.0  # Default weight
            for category, category_weight in AGENT_WEIGHTS.items():
                if category in agent_name.lower():
                    weight = category_weight
                    break
            
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
            
            if decision == "BUY":
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
            # Determine weighted consensus direction
            max_weight = max(buy_weight, sell_weight, hold_weight)
            if max_weight == buy_weight and buy_weight > 0:
                consensus_direction = "BUY"
            elif max_weight == sell_weight and sell_weight > 0:
                consensus_direction = "SELL"
            else:
                consensus_direction = "HOLD"
            
            # Calculate weighted signal strength (0.0 to 1.0)
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
                "total_agents": total_agents,
                "total_weight": total_weight
            },
            "weighted_votes": {
                "buy": round(buy_weight, 2),
                "sell": round(sell_weight, 2),
                "hold": round(hold_weight, 2)
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

    async def _generate_llm_decision(self, aggregated: Dict[str, Any], context: Dict[str, Any]) -> AnalysisResult:
        """Generate final trading decision using LLM analysis."""
        try:
            prompt = self._build_decision_prompt(aggregated, context)

            # Import here to avoid circular dependencies
            from genai_module.contracts import LLMRequest

            llm_request = LLMRequest(
                prompt=prompt,
                model=os.getenv("LLM_DECISION_MODEL", os.getenv("LLM_MODEL")),
                temperature=0.1,  # Low temperature for consistent decisions
                max_tokens=1000
            )

            llm_response = await self.llm_client.generate(llm_request)

            # Parse LLM response
            return self._parse_llm_response(llm_response, aggregated)

        except Exception as e:
            # Log full stack so provider/LLM issues are easier to diagnose
            logger.exception(f"LLM decision generation failed: {e}")
            return self._generate_fallback_decision(aggregated, True)

    def _build_decision_prompt(self, aggregated: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Build comprehensive LLM prompt for options trading decision with weighted voting context."""
        instrument = context.get("instrument", "BANKNIFTY")
        market_hours = context.get("market_hours", False)
        
        # Extract weighted voting details
        weighted_votes = aggregated.get('weighted_votes', {})
        risk_veto = aggregated.get('risk_veto', {})
        bull_bear_signals = aggregated.get('bull_bear_signals', [])

        prompt = f"""You are an expert options trader analyzing {instrument} for the next 15-minute period.

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
8. Provide specific options strategy with reasoning
9. Include confidence level and risk management notes

Respond in this exact JSON format:
{{
  "decision": "BUY_CALL|BUY_PUT|IRON_CONDOR|HOLD",
  "confidence": 0.0-1.0,
  "strategy": "detailed options strategy description",
  "reasoning": "comprehensive analysis explanation with weighted vote consideration",
  "risk_notes": "position sizing and risk management",
  "timeframe": "next 15 minutes to 1 hour",
  "entry_conditions": "specific conditions to wait for"
}}
"""

        return prompt

    def _parse_llm_response(self, llm_response: Any, aggregated: Dict[str, Any]) -> AnalysisResult:
        """Parse LLM response into AnalysisResult."""
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

            return AnalysisResult(
                decision=parsed.get("decision", "HOLD"),
                confidence=float(parsed.get("confidence", 0.0)),
                details={
                    **parsed,
                    "llm_generated": True,
                    "aggregated_analysis": aggregated
                }
            )

        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return self._generate_fallback_decision(aggregated, True)

    def _generate_fallback_decision(self, aggregated: Dict[str, Any], market_hours: bool) -> AnalysisResult:
        """Generate fallback decision when LLM is unavailable."""
        direction = aggregated.get('consensus_direction', 'HOLD')
        strength = aggregated.get('signal_strength', 0.0)
        risk = aggregated.get('risk_assessment', 'UNKNOWN')

        # Conservative fallback logic
        if not market_hours:
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

        return AnalysisResult(
            decision=decision,
            confidence=confidence,
            details={
                "reasoning": reasoning,
                "fallback_mode": True,
                "aggregated_analysis": aggregated,
                "market_hours": market_hours,
                "risk_adjusted": True
            }
        )

