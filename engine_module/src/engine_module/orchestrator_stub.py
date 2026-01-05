"""Orchestrator stub implementation for trading engine.

This module provides a skeleton TradingOrchestrator that demonstrates
dependency injection and async execution flow. Implementation details
are left as TODOs for incremental development.
"""

import logging
from typing import Any, Dict, Optional, Protocol, runtime_checkable
from datetime import datetime, timedelta

from .contracts import AnalysisResult

logger = logging.getLogger(__name__)


# Import contracts from other modules via duck typing
# (avoid hard dependencies on other modules in implementation)
@runtime_checkable
class LLMClient(Protocol):
    """LLM client protocol for type hints."""
    async def request(self, request: Any) -> Any:
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
        market_store: MarketStore,
        options_data: OptionsData,
        agents: Optional[list[Agent]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize orchestrator with injected dependencies.
        
        Args:
            llm_client: GenAI client for LLM requests
            market_store: Data source for market ticks/OHLC
            options_data: Source for options chain data
            agents: List of analysis agents (technical, sentiment, etc.)
            **kwargs: Additional config (e.g., instruments, lookback_days)
        """
        self.llm_client = llm_client
        self.market_store = market_store
        self.options_data = options_data
        self.agents = agents or []
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
        timestamp = context.get("timestamp", datetime.now())
        market_hours = context.get("market_hours", False)
        cycle_interval = context.get("cycle_interval", "15min")

        logger.info(f"Starting {cycle_interval} analysis cycle for {instrument}")

        try:
            # Step 1: Fetch market data (15min OHLC + recent ticks)
            market_data = await self._fetch_market_data(instrument)

            # Step 2: Fetch options chain data
            options_chain = await self._fetch_options_data(instrument)

            # Step 3: Run all agents in parallel
            agent_results = await self._run_agents_parallel(market_data, options_chain, context)

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
            final_decision.details.update({
                "instrument": instrument,
                "timestamp": timestamp.isoformat(),
                "market_hours": market_hours,
                "cycle_interval": cycle_interval,
                "agents_run": len(agent_results),
                "data_points": len(market_data.get("ohlc", [])),
                "options_expiries": len(options_chain.get("expiries", [])) if options_chain else 0,
                "analysis_duration_seconds": (datetime.now() - timestamp).total_seconds()
            })

            logger.info(f"Completed analysis cycle: {final_decision.decision} "
                       f"(confidence: {final_decision.confidence:.1%})")

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
            # Get recent ticks (last 100)
            ticks = await self.market_store.get_latest_ticks(instrument, limit=100)

            # Get 15min OHLC data (last 24 hours = 96 bars)
            # This covers the last trading day for intraday analysis
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
            # Get nearest expiry options chain
            chain_data = await self.options_data.fetch_chain(instrument)

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

    async def _run_agents_parallel(self, market_data: Dict[str, Any],
                                 options_data: Dict[str, Any],
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
            "options_chain": options_data,  # Alias for backward compatibility
            "market_data": market_data      # Alias for backward compatibility
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
        """Aggregate multiple agent results into unified options trading view."""
        if not agent_results:
            return {
                "signal_strength": 0.0,
                "consensus_direction": "NEUTRAL",
                "confidence_score": 0.0,
                "risk_assessment": "UNKNOWN",
                "key_insights": [],
                "options_strategy": "HOLD"
            }

        # Initialize aggregation
        buy_signals = 0
        sell_signals = 0
        hold_signals = 0
        total_confidence = 0.0

        technical_signals = []
        sentiment_signals = []
        macro_signals = []
        risk_signals = []
        execution_signals = []

        # Analyze each agent result
        for result in agent_results:
            confidence = result.confidence
            total_confidence += confidence

            # Categorize by decision
            if result.decision.upper() == "BUY":
                buy_signals += 1
            elif result.decision.upper() == "SELL":
                sell_signals += 1
            else:
                hold_signals += 1

            # Extract agent-specific insights
            agent_name = getattr(result, '_agent_name', 'Unknown')
            details = result.details or {}

            if 'technical' in agent_name.lower():
                technical_signals.append({
                    "agent": agent_name,
                    "signal": result.decision,
                    "confidence": confidence,
                    "indicators": details
                })
            elif 'sentiment' in agent_name.lower():
                sentiment_signals.append({
                    "agent": agent_name,
                    "signal": result.decision,
                    "confidence": confidence,
                    "sentiment": details.get('aggregate_sentiment', 0.0)
                })
            elif 'macro' in agent_name.lower():
                macro_signals.append({
                    "agent": agent_name,
                    "signal": result.decision,
                    "confidence": confidence,
                    "indicators": details
                })
            elif 'risk' in agent_name.lower():
                risk_signals.append({
                    "agent": agent_name,
                    "signal": result.decision,
                    "confidence": confidence,
                    "risk_level": details.get('risk_level', 'UNKNOWN')
                })
            elif 'execution' in agent_name.lower():
                execution_signals.append({
                    "agent": agent_name,
                    "signal": result.decision,
                    "confidence": confidence,
                    "execution_readiness": details.get('execution_ready', False)
                })

        # Calculate consensus
        total_agents = len(agent_results)
        avg_confidence = total_confidence / total_agents if total_agents > 0 else 0.0

        # Determine consensus direction
        max_signals = max(buy_signals, sell_signals, hold_signals)
        if max_signals == buy_signals and buy_signals > total_agents * 0.4:
            consensus_direction = "BUY"
        elif max_signals == sell_signals and sell_signals > total_agents * 0.4:
            consensus_direction = "SELL"
        else:
            consensus_direction = "HOLD"

        # Calculate signal strength (0.0 to 1.0)
        signal_strength = max_signals / total_agents if total_agents > 0 else 0.0

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

        # Compile key insights
        key_insights = []
        if technical_signals:
            key_insights.append(f"Technical: {len([s for s in technical_signals if s['signal'] == consensus_direction])}/{len(technical_signals)} support {consensus_direction}")
        if sentiment_signals:
            avg_sentiment = sum(s['sentiment'] for s in sentiment_signals) / len(sentiment_signals)
            key_insights.append(f"Sentiment: {avg_sentiment:.2f} (market mood)")
        if macro_signals:
            key_insights.append(f"Macro: {len([s for s in macro_signals if s['signal'] == consensus_direction])}/{len(macro_signals)} support {consensus_direction}")

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
                "total_agents": total_agents
            },
            "technical_signals": technical_signals,
            "sentiment_signals": sentiment_signals,
            "macro_signals": macro_signals,
            "risk_signals": risk_signals,
            "execution_signals": execution_signals,
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
                model="gpt-4o",  # Use configured model
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistent decisions
                max_tokens=1000
            )

            llm_response = await self.llm_client.request(llm_request)

            # Parse LLM response
            return self._parse_llm_response(llm_response, aggregated)

        except Exception as e:
            logger.error(f"LLM decision generation failed: {e}")
            return self._generate_fallback_decision(aggregated, True)

    def _build_decision_prompt(self, aggregated: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Build comprehensive LLM prompt for options trading decision."""
        instrument = context.get("instrument", "BANKNIFTY")
        market_hours = context.get("market_hours", False)

        prompt = f"""You are an expert options trader analyzing {instrument} for the next 15-minute period.

MARKET ANALYSIS SUMMARY:
- Signal Strength: {aggregated['signal_strength']:.1%}
- Consensus Direction: {aggregated['consensus_direction']}
- Average Confidence: {aggregated['confidence_score']:.1%}
- Risk Assessment: {aggregated['risk_assessment']}
- Agent Breakdown: {aggregated['agent_breakdown']['buy_signals']} BUY, {aggregated['agent_breakdown']['sell_signals']} SELL, {aggregated['agent_breakdown']['hold_signals']} HOLD

KEY INSIGHTS:
{chr(10).join(f"- {insight}" for insight in aggregated['key_insights'])}

TECHNICAL ANALYSIS:
{chr(10).join(f"- {sig['agent']}: {sig['signal']} ({sig['confidence']:.1%})" for sig in aggregated['technical_signals'][:3])}

SENTIMENT ANALYSIS:
{chr(10).join(f"- {sig['agent']}: {sig['signal']} (sentiment: {sig['sentiment']:.2f})" for sig in aggregated['sentiment_signals'][:2])}

MACRO ANALYSIS:
{chr(10).join(f"- {sig['agent']}: {sig['signal']} ({sig['confidence']:.1%})" for sig in aggregated['macro_signals'][:2])}

RISK ASSESSMENT:
{chr(10).join(f"- {sig['agent']}: {sig['signal']} (risk: {sig.get('risk_level', 'UNKNOWN')})" for sig in aggregated['risk_signals'][:2])}

CURRENT RECOMMENDATION: {aggregated['options_strategy']}

INSTRUCTIONS:
1. Analyze all signals and provide a final options trading decision
2. Consider market hours: {'OPEN' if market_hours else 'CLOSED'}
3. Factor in risk assessment and position sizing
4. Provide specific options strategy with reasoning
5. Include confidence level and risk management notes

Respond in this exact JSON format:
{
  "decision": "BUY_CALL|BUY_PUT|IRON_CONDOR|HOLD",
  "confidence": 0.0-1.0,
  "strategy": "detailed options strategy description",
  "reasoning": "comprehensive analysis explanation",
  "risk_notes": "position sizing and risk management",
  "timeframe": "next 15 minutes to 1 hour",
  "entry_conditions": "specific conditions to wait for"
}
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
