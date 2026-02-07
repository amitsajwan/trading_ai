"""Enhanced trading orchestrator with mode-aware execution.

This orchestrator supports LIVE, PAPER, and BACKTEST modes as specified
in the trading system specification.
"""

import logging
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
from dataclasses import dataclass
import numpy as np

from .contracts import Orchestrator, TradingDecision, AnalysisResult
from .api import build_orchestrator
from .execution_adapters import create_execution_adapter, ExecutionAdapter
from .services.position_manager import PositionManager
import redis
from .signal_creator import create_signals_from_decision, save_signal_to_mongodb, cancel_pending_signals
from .signal_monitor import SignalTriggerEvent

logger = logging.getLogger(__name__)

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


def get_current_time(redis_client: Optional[Any] = None) -> datetime:
    """Get current time, considering virtual time mode for backtesting.

    In backtest/historical mode, uses virtual time from Redis if available.
    Otherwise uses real current time.

    Args:
        redis_client: Redis client to check for virtual time

    Returns:
        Current datetime (IST timezone)
    """
    if redis_client:
        try:
            # Check if virtual time is enabled
            virtual_enabled = redis_client.get("system:virtual_time:enabled")
            if virtual_enabled and virtual_enabled.decode() == "1":
                virtual_time_str = redis_client.get("system:virtual_time:current")
                if virtual_time_str:
                    virtual_time = datetime.fromisoformat(virtual_time_str.decode())
                    # Ensure it's in IST
                    if virtual_time.tzinfo is None:
                        virtual_time = virtual_time.replace(tzinfo=IST)
                    else:
                        virtual_time = virtual_time.astimezone(IST)
                    return virtual_time
        except Exception as e:
            # If Redis fails, fall back to real time
            pass

    # Default to real current time
    return datetime.now(IST)


def convert_numpy_types(obj):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        # For objects, convert their __dict__
        result = {}
        for key, value in obj.__dict__.items():
            if not key.startswith('_'):  # Skip private attributes
                result[key] = convert_numpy_types(value)
        return result
    else:
        return obj


@dataclass
class TradingContext:
    """Context for trading execution including instrument, mode, and metadata."""
    instrument: str
    mode: str
    run_id: Optional[str] = None


class EnhancedTradingOrchestrator(Orchestrator):
    """Enhanced orchestrator with mode-aware execution support."""

    def __init__(
        self,
        agents: List[Any],
        context: TradingContext,
        llm_client=None,
        market_data_provider=None,
        options_data_provider=None,
        news_data_provider=None,
        technical_data_provider=None,
        fundamental_data_provider=None,
        macro_data_provider=None,
        signal_monitor=None,
        position_provider=None,
        mongo_db=None,
        execution_adapter=None,
        redis_client: Optional[redis.Redis] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize enhanced orchestrator.

        Args:
            agents: List of analysis agents
            context: Trading context containing instrument, mode, and run metadata
            llm_client: LLM client for AI-powered analysis
            market_data_provider: Provider for market data
            options_data_provider: Provider for options data
            news_data_provider: Provider for news and sentiment data
            technical_data_provider: Provider for technical indicators
            fundamental_data_provider: Provider for fundamental data
            macro_data_provider: Provider for macroeconomic data
            signal_monitor: Monitor for trading signals
            position_provider: Provider for position data
            mongo_db: MongoDB client for persistence
            execution_adapter: Adapter for executing trades
            redis_client: Redis client for pub/sub
        """
        self.agents = agents
        self.context = context
        self.run_id = context.run_id  # For backward compatibility
        self.llm_client = llm_client
        self.market_data_provider = market_data_provider
        self.options_data_provider = options_data_provider
        self.news_data_provider = news_data_provider
        self.technical_data_provider = technical_data_provider
        self.fundamental_data_provider = fundamental_data_provider
        self.macro_data_provider = macro_data_provider
        self.signal_monitor = signal_monitor
        self.position_provider = position_provider
        self.mongo_db = mongo_db
        self.redis_client = redis_client
        self.config = config or {}

        # Use provided execution adapter or create one based on mode
        if execution_adapter:
            self.execution_adapter = execution_adapter
        else:
            self.execution_adapter = create_execution_adapter(self.context.mode, self.context.run_id, redis_client, mongo_db)

        # Initialize position manager if needed
        self.position_manager = PositionManager() if position_provider else None

        # Auto-execute signals when they trigger (optional)
        try:
            auto_exec = bool(self.config.get("auto_execute_signals", False))
            if auto_exec and self.signal_monitor and hasattr(self.signal_monitor, "set_execution_callback"):
                self.signal_monitor.set_execution_callback(self._on_signal_triggered)
                logger.info("EnhancedTradingOrchestrator: auto_execute_signals enabled (callback registered)")
        except Exception:
            pass

        logger.info(f"EnhancedTradingOrchestrator initialized for {self.context.instrument} in {self.context.mode} mode (run_id: {self.context.run_id})")

    async def run_cycle(self, context: Dict[str, Any]) -> TradingDecision:
        """Run complete analysis cycle with research-first architecture.

        Phase 1: Research Manager establishes primary thesis
        Phase 2: Supporting agents provide evidence and validation
        Phase 3: Risk assessment and final decision validation
        """
        try:
            instrument = context.get("instrument", self.context.instrument)

            # Ensure context has the correct instrument for data providers
            context["instrument"] = instrument

            # 0) Invalidate previous signals for this instrument (15-min cadence)
            try:
                if self.mongo_db is not None:
                    await cancel_pending_signals(self.mongo_db, instrument=instrument, reason="cycle_invalidation")
            except Exception as e:
                logger.debug(f"Signal invalidation (Mongo) skipped/failed: {e}")

            try:
                if self.signal_monitor and hasattr(self.signal_monitor, "remove_signals_for_instrument"):
                    self.signal_monitor.remove_signals_for_instrument(instrument)
            except Exception as e:
                logger.debug(f"Signal invalidation (monitor) skipped/failed: {e}")

            # PHASE 1: Get core data required by all agents
            technical_data = await self._get_technical_data(context)
            ohlc_data = await self._get_ohlc_data(context)
            news_data = await self._get_news_data(context)
            fundamental_data = await self._get_fundamental_data(context)
            macro_data = await self._get_macro_data(context)

            # Get current positions for context-aware decisions
            positions = []
            try:
                if self.position_provider and hasattr(self.position_provider, "get_positions"):
                    positions = await self.position_provider.get_positions(symbol=instrument)
            except Exception:
                positions = []
            context["positions"] = positions

            # PHASE 2: Research Manager establishes primary thesis FIRST
            research_decision = await self._run_research_manager_first(context, technical_data, ohlc_data, news_data, fundamental_data, macro_data)

            # PHASE 3: Supporting agents provide evidence and validation for the thesis
            supporting_results = await self._run_supporting_agents(context, technical_data, ohlc_data, news_data, fundamental_data, macro_data, research_decision)

            # Combine research and supporting results
            all_agent_results = [research_decision] + supporting_results if research_decision else supporting_results

            # PHASE 4: Risk assessment and final validation
            final_decision = await self._validate_and_finalize_decision(research_decision, supporting_results, context)

            # Publish agent results to WebSocket for UI
            await self._publish_agent_results(all_agent_results, context)

            # Publish final decision to WebSocket for UI
            await self._publish_final_decision(final_decision, all_agent_results, context)

            # Create signals from decision details (structured preferred)
            execution_result = None
            try:
                ar = AnalysisResult(
                    decision=final_decision.get("decision", "HOLD"),
                    confidence=float(final_decision.get("confidence", 0.0)),
                    details=final_decision.get("details", {}) if isinstance(final_decision.get("details"), dict) else {"reasoning": final_decision.get("reasoning", "")},
                    agent="ResearchFirstOrchestrator"
                )
                sigs = create_signals_from_decision(
                    analysis_result=ar,
                    instrument=instrument,
                    technical_indicators=technical_data,
                    current_price=context.get("current_price"),
                    redis_client=self.redis_client
                )
                if sigs:
                    # Persist + add to monitor
                    for s in sigs:
                        try:
                            if self.mongo_db is not None:
                                await save_signal_to_mongodb(s, self.mongo_db)
                        except Exception:
                            pass
                        try:
                            if self.signal_monitor:
                                self.signal_monitor.add_signal(s)
                        except Exception:
                            pass
                    # attach for UI
                    final_decision.setdefault("details", {})
                    if isinstance(final_decision["details"], dict):
                        final_decision["details"]["signals_created"] = len(sigs)
                        final_decision["details"]["signal_ids"] = [s.condition_id for s in sigs]
            except Exception as e:
                logger.debug(f"Signal creation skipped/failed: {e}")

            # Optional immediate execution path (kept off by default if using signals)
            if not self.signal_monitor and self.config.get("auto_execute_signals", False):
                execution_result = await self._execute_decision(final_decision, context)

            # Create comprehensive trading decision
            trading_decision = TradingDecision(
                instrument=instrument,
                decision=final_decision.get("decision", "HOLD"),
                confidence=final_decision.get("confidence", 0.0),
                timestamp=get_current_time(self.redis_client),
                reasoning=final_decision.get("reasoning", ""),
                agent_results=all_agent_results,
                technical_indicators=technical_data,
                execution_result=execution_result,
                mode=self.context.mode,
                run_id=self.run_id
            )

            logger.info(f"Research-first orchestrator cycle completed: {trading_decision.decision} ({trading_decision.confidence:.2f}) in {self.context.mode} mode")
            return trading_decision

            # Publish final decision to WebSocket for UI
            await self._publish_final_decision(decision, agent_results, context)

            # Create signals from decision details (structured preferred)
            execution_result = None
            try:
                ar = AnalysisResult(
                    decision=decision.get("decision", "HOLD"),
                    confidence=float(decision.get("confidence", 0.0)),
                    details=decision.get("details", {}) if isinstance(decision.get("details"), dict) else {"reasoning": decision.get("reasoning", "")},
                    agent="FinalJudge"
                )
                sigs = create_signals_from_decision(
                    analysis_result=ar,
                    instrument=instrument,
                    technical_indicators=technical_data,
                    current_price=context.get("current_price"),
                    redis_client=self.redis_client
                )
                if sigs:
                    # Persist + add to monitor
                    for s in sigs:
                        try:
                            if self.mongo_db is not None:
                                await save_signal_to_mongodb(s, self.mongo_db)
                        except Exception:
                            pass
                        try:
                            if self.signal_monitor:
                                self.signal_monitor.add_signal(s)
                        except Exception:
                            pass
                    # attach for UI
                    decision.setdefault("details", {})
                    if isinstance(decision["details"], dict):
                        decision["details"]["signals_created"] = len(sigs)
                        decision["details"]["signal_ids"] = [s.condition_id for s in sigs]
            except Exception as e:
                logger.debug(f"Signal creation skipped/failed: {e}")

            # Optional immediate execution path (kept off by default if using signals)
            if not self.signal_monitor and self.config.get("auto_execute_signals", False):
                execution_result = await self._execute_decision(decision, context)

            # Create comprehensive trading decision
            trading_decision = TradingDecision(
                instrument=instrument,
                decision=decision.get("decision", "HOLD"),
                confidence=decision.get("confidence", 0.0),
                timestamp=datetime.now(IST),
                reasoning=decision.get("reasoning", ""),
                agent_results=agent_results,
                technical_indicators=technical_data,
                execution_result=execution_result,
                mode=self.context.mode,
                run_id=self.run_id
            )

            logger.info(f"Orchestrator cycle completed: {trading_decision.decision} ({trading_decision.confidence:.2f}) in {self.context.mode} mode")
            return trading_decision

        except Exception as e:
            logger.error(f"Orchestrator cycle failed: {e}", exc_info=True)
            return TradingDecision(
                instrument=context.get("instrument", "UNKNOWN"),
                decision="HOLD",
                confidence=0.0,
                timestamp=get_current_time(self.redis_client),
                reasoning=f"Error: {str(e)}",
                agent_results=[],
                technical_indicators={},
                execution_result=None,
                mode=self.context.mode,
                run_id=self.run_id
            )

    async def _run_research_manager_first(self, context: Dict[str, Any], technical_data: Dict[str, Any],
                                         ohlc_data: List[Dict[str, Any]], news_data: Dict[str, Any],
                                         fundamental_data: Dict[str, Any], macro_data: Dict[str, Any]) -> Optional[AnalysisResult]:
        """Phase 2: Run EnhancedResearchManager first to establish primary thesis.

        This is the foundation of the research-first architecture. The research manager
        establishes the core bull/bear/neutral thesis that all other analysis supports.
        """
        try:
            # Check if EnhancedResearchManager is available in agents
            research_manager = None
            for agent in self.agents:
                if agent.__class__.__name__ == "EnhancedResearchManager":
                    research_manager = agent
                    break

            if not research_manager:
                logger.warning("EnhancedResearchManager not found in agents - falling back to traditional approach")
                return None

            # Prepare context specifically for research manager
            research_context = context.copy()
            research_context["technical_indicators"] = technical_data
            research_context["current_price"] = technical_data.get("current_price", 0)
            if ohlc_data:
                research_context["ohlc"] = ohlc_data
            if news_data:
                research_context.update(news_data)
            if fundamental_data:
                research_context.update(fundamental_data)
            if macro_data:
                research_context.update(macro_data)

            # Run research manager to establish primary thesis
            research_result = await self._run_single_agent(research_manager, research_context)

            if research_result and research_result.confidence > 0.3:  # Minimum confidence threshold
                logger.info(f"Research Manager thesis established: {research_result.decision} (confidence: {research_result.confidence:.2f})")
                return research_result
            else:
                logger.info("Research Manager returned low-confidence result - proceeding with supporting analysis only")
                return None

        except Exception as e:
            logger.warning(f"Research manager execution failed: {e}")
            return None

    async def _run_supporting_agents(self, context: Dict[str, Any], technical_data: Dict[str, Any],
                                   ohlc_data: List[Dict[str, Any]], news_data: Dict[str, Any],
                                   fundamental_data: Dict[str, Any], macro_data: Dict[str, Any],
                                   research_decision: Optional[AnalysisResult]) -> List[AnalysisResult]:
        """Phase 3: Run supporting agents to validate and enhance the research thesis.

        Supporting agents provide evidence that either confirms or challenges the
        research manager's thesis, leading to more robust decision-making.
        """
        # Prepare agent context with research thesis for context-aware analysis
        agent_context = context.copy()
        agent_context["technical_indicators"] = technical_data
        agent_context["current_price"] = technical_data.get("current_price", 0)

        if ohlc_data:
            agent_context["ohlc"] = ohlc_data
        if news_data:
            agent_context.update(news_data)
        if fundamental_data:
            agent_context.update(fundamental_data)
        if macro_data:
            agent_context.update(macro_data)

        # Add research thesis to context for supporting agents
        if research_decision:
            agent_context["research_thesis"] = {
                "decision": research_decision.decision,
                "confidence": research_decision.confidence,
                "thesis": research_decision.details.get("research_plan", "") if research_decision.details else ""
            }

            # Extract individual trader results for agents that need them
            bull_result = research_decision.details.get("bull_trader_input") if research_decision.details else None
            bear_result = research_decision.details.get("bear_trader_input") if research_decision.details else None

            if bull_result:
                agent_context["bull_researcher"] = bull_result
            if bear_result:
                agent_context["bear_researcher"] = bear_result

            # Pass the market maker synthesis
            agent_context["market_maker"] = research_decision

        # Special context for SignalCreationAgent - it needs all agent results
        # We'll handle this after running other agents

        # Define supporting agent types (exclude research managers and signal creation)
        supporting_agent_types = {
            "TechnicalAgent", "VolumeAgent", "MomentumAgent", "TrendAgent",
            "MeanReversionAgent", "SentimentAgent", "FundamentalAgent", "MacroAgent",
            "PortfolioManagerAgent", "RiskAgent", "EnhancedRiskAgent"
        }

        logger.debug(f"Looking for supporting agents of types: {supporting_agent_types}")

        # Include specialized agents based on research thesis
        if research_decision:
            decision_upper = research_decision.decision.upper()
            # Include OptionsStrategyAgent for options trading (BANKNIFTY26JANFUT is options)
            instrument = context.get("instrument", "")
            if "BANKNIFTY26JANFUT" in instrument or any(x in decision_upper for x in ["CALL", "PUT", "IRON_CONDOR", "SPREAD", "OPTION"]):
                supporting_agent_types.add("OptionsStrategyAgent")
            # Always include SignalCreationAgent for final signal synthesis
            supporting_agent_types.add("SignalCreationAgent")

        # Separate SignalCreationAgent from other supporting agents
        signal_creation_agent = None
        regular_supporting_agents = []

        for agent in self.agents:
            agent_name = agent.__class__.__name__
            if agent_name == "SignalCreationAgent":
                signal_creation_agent = agent
                logger.debug(f"Found SignalCreationAgent: {agent}")
            elif agent_name in supporting_agent_types:
                regular_supporting_agents.append(agent)
                logger.debug(f"Found supporting agent: {agent_name}")

        logger.info(f"Found {len(regular_supporting_agents)} regular supporting agents and SignalCreationAgent: {signal_creation_agent is not None}")

        if not regular_supporting_agents and not signal_creation_agent:
            logger.warning("No supporting agents found")
            return []

        # Run regular supporting agents concurrently
        logger.debug(f"Running {len(regular_supporting_agents)} supporting agents concurrently")
        tasks = [self._run_single_agent(agent, agent_context) for agent in regular_supporting_agents]
        supporting_results = await asyncio.gather(*tasks, return_exceptions=True)
        logger.debug(f"Supporting agents execution completed, got {len(supporting_results)} results")

        # Run SignalCreationAgent with all other agent results
        if signal_creation_agent:
            signal_context = agent_context.copy()
            signal_context["agent_results"] = [r for r in supporting_results if isinstance(r, AnalysisResult)]
            signal_context["current_positions"] = context.get("current_positions", [])
            signal_context["cash_available"] = context.get("cash_available", 1000000)
            signal_context["volatility"] = technical_data.get("volatility", 0.15)

            signal_result = await self._run_single_agent(signal_creation_agent, signal_context)
            if isinstance(signal_result, AnalysisResult):
                supporting_results.append(signal_result)

        # Filter valid results
        valid_results = []
        for i, result in enumerate(supporting_results):
            if isinstance(result, Exception):
                agent_name = regular_supporting_agents[i].__class__.__name__ if i < len(regular_supporting_agents) else "Unknown"
                logger.warning(f"Supporting agent {agent_name} failed: {result}")
                continue
            valid_results.append(result)

        logger.info(f"Supporting agents completed: {len(valid_results)}/{len(regular_supporting_agents)} successful")
        return valid_results

    async def _validate_and_finalize_decision(self, research_decision: Optional[AnalysisResult],
                                            supporting_results: List[AnalysisResult],
                                            context: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 4: Validate research thesis with supporting evidence and finalize decision.

        This method implements trader-focused decision logic:
        1. Research thesis is primary driver
        2. Supporting agents provide validation/confirmation
        3. LLM provides risk assessment but doesn't override strong research conclusions
        """
        instrument = context.get("instrument", self.context.instrument)

        # Case 1: Strong research thesis with supporting validation
        if research_decision and research_decision.confidence >= 0.6:
            # Research thesis is strong - use it as foundation
            supporting_validation = self._assess_supporting_validation(research_decision, supporting_results)

            # If supporting agents mostly agree, confidence increases
            if supporting_validation["agreement_ratio"] >= 0.6:
                adjusted_confidence = min(research_decision.confidence * 1.2, 0.95)
                decision = research_decision.decision
                reasoning = f"Strong research thesis ({research_decision.decision}) validated by {supporting_validation['supporting_votes']}/{len(supporting_results)} supporting agents"
            else:
                # Supporting agents disagree - reduce confidence but don't override
                adjusted_confidence = research_decision.confidence * 0.8
                decision = research_decision.decision
                reasoning = f"Research thesis ({research_decision.decision}) with moderate supporting validation ({supporting_validation['supporting_votes']}/{len(supporting_results)} agents)"

            # LLM risk assessment (doesn't override)
            llm_assessment = await self._get_llm_risk_assessment(research_decision, supporting_results, context)

            # Include structured signals from SignalCreationAgent if available
            details = {
                "research_thesis": research_decision.details,
                "supporting_validation": supporting_validation,
                "llm_risk_assessment": llm_assessment,
                "decision_framework": "research_first_validated",
                "valid_for_minutes": 15
            }

            # Use signals from SignalCreationAgent if available
            signal_creation_result = None
            for result in supporting_results:
                if getattr(result, 'agent', '') == 'SignalCreationAgent' and result.details:
                    signal_creation_result = result
                    break

            if signal_creation_result and signal_creation_result.details.get('signals'):
                details["signals"] = signal_creation_result.details["signals"]
                logger.info(f"Included {len(signal_creation_result.details['signals'])} final signals from SignalCreationAgent")

                # Update confidence based on signal creation
                if signal_creation_result.confidence > 0:
                    adjusted_confidence = signal_creation_result.confidence
                    reasoning = signal_creation_result.details.get('reasoning', reasoning)
            else:
                logger.warning("No signals created by SignalCreationAgent")

            return {
                "decision": decision,
                "confidence": adjusted_confidence,
                "reasoning": reasoning,
                "details": details
            }

        # Case 2: Weak/No research thesis - fall back to supporting agent consensus
        else:
            # Aggregate supporting agent decisions
            aggregated = await self._aggregate_decisions(supporting_results)

            # LLM final validation
            if self.llm_client and aggregated.get("confidence", 0.0) >= 0.4:
                llm_decision = await self._judge_decision(aggregated, supporting_results, context)
                return llm_decision
            else:
                return aggregated

    def _assess_supporting_validation(self, research_decision: AnalysisResult,
                                    supporting_results: List[AnalysisResult]) -> Dict[str, Any]:
        """Assess how well supporting agents validate the research thesis."""
        if not supporting_results:
            return {"agreement_ratio": 0.0, "supporting_votes": 0, "conflicting_votes": 0, "excluded_agents": 0}

        # Separate participating and excluded agents
        participating_results = [r for r in supporting_results if not getattr(r, 'excluded', False)]
        excluded_results = [r for r in supporting_results if getattr(r, 'excluded', False)]

        if not participating_results:
            return {
                "agreement_ratio": 0.0,
                "supporting_votes": 0,
                "conflicting_votes": 0,
                "total_agents": len(supporting_results),
                "participating_agents": 0,
                "excluded_agents": len(excluded_results)
            }

        supporting_votes = 0
        conflicting_votes = 0

        research_direction = self._extract_direction_from_decision(research_decision.decision)

        for result in participating_results:
            agent_direction = self._extract_direction_from_decision(result.decision)

            # Direction agreement (simplified logic)
            if research_direction == agent_direction and result.confidence >= 0.5:
                supporting_votes += 1
            elif research_direction != agent_direction and result.confidence >= 0.6:
                conflicting_votes += 1

        total_valid_agents = len([r for r in participating_results if r.confidence >= 0.4])
        agreement_ratio = supporting_votes / max(total_valid_agents, 1)

        return {
            "agreement_ratio": agreement_ratio,
            "supporting_votes": supporting_votes,
            "conflicting_votes": conflicting_votes,
            "total_agents": len(supporting_results),
            "participating_agents": len(participating_results),
            "excluded_agents": len(excluded_results)
        }

    def _extract_direction_from_decision(self, decision: str) -> str:
        """Extract directional bias from agent decision."""
        decision = decision.upper() if decision else "HOLD"

        if "BUY" in decision or "BULL" in decision:
            return "BULLISH"
        elif "SELL" in decision or "BEAR" in decision:
            return "BEARISH"
        else:
            return "NEUTRAL"

    async def _get_llm_risk_assessment(self, research_decision: AnalysisResult,
                                     supporting_results: List[AnalysisResult],
                                     context: Dict[str, Any]) -> Dict[str, Any]:
        """Get LLM risk assessment without overriding the research decision."""
        if not self.llm_client:
            return {"risk_level": "unknown", "assessment": "No LLM available"}

        try:
            prompt = f"""
            Analyze the risk profile of this trading decision. DO NOT override the research thesis.

            Research Decision: {research_decision.decision} (confidence: {research_decision.confidence:.2f})
            Thesis: {research_decision.details.get('research_plan', 'N/A') if research_decision.details else 'N/A'}

            Supporting agents: {len([r for r in supporting_results if r.confidence >= 0.5])}/{len(supporting_results)} agree

            Context: {context.get('instrument', 'UNKNOWN')} at price {context.get('current_price', 'N/A')}

            Provide risk assessment focusing on:
            1. Position sizing recommendation (0.5-2.0x normal)
            2. Stop loss tightness (conservative/moderate/aggressive)
            3. Holding period expectation
            4. Key risk factors to monitor

            Return as JSON with keys: risk_level, position_size_multiplier, stop_loss_style, holding_period, key_risks
            """

            from genai_module.contracts import LLMRequest
            req = LLMRequest(prompt=prompt, temperature=0.1, max_tokens=300)
            resp = await self.llm_client.generate(req)
            content = getattr(resp, "content", None) or getattr(resp, "text", None) or "{}"

            import json
            assessment = json.loads(content)
            return assessment

        except Exception as e:
            logger.debug(f"LLM risk assessment failed: {e}")
            return {"risk_level": "moderate", "assessment": "Assessment unavailable"}

    async def _judge_decision(self, aggregated: Dict[str, Any], agent_results: List[AnalysisResult], context: Dict[str, Any]) -> Dict[str, Any]:
        """LLM-backed final judge that outputs structured signals + English reasoning."""
        # If no LLM client, fall back to aggregated summary
        if not self.llm_client:
            return aggregated

        instrument = context.get("instrument", self.context.instrument)
        positions = context.get("positions", [])

        # Build agent block
        lines = []
        for r in agent_results:
            an = getattr(r, "agent", None) or getattr(r, "_agent_name", None) or r.__class__.__name__
            dec = getattr(r, "decision", "HOLD")
            conf = float(getattr(r, "confidence", 0.0) or 0.0)
            det = getattr(r, "details", {}) or {}
            reasoning = det.get("reasoning") if isinstance(det, dict) else ""
            lines.append(f"- {an}: decision={dec}, confidence={conf:.2f}, reasoning={reasoning or 'n/a'}")
        agent_block = "\n".join(lines) if lines else "- (no agents)"

        # Positions block
        pos_lines = []
        if isinstance(positions, list):
            for p in positions[:10]:
                if not isinstance(p, dict):
                    continue
                pos_lines.append(
                    f"- side={p.get('action')}, qty={p.get('quantity')}, entry={p.get('entry_price')}, current={p.get('current_price')}"
                )
        pos_block = "\n".join(pos_lines) if pos_lines else "No open positions."

        prompt = f"""You are the FINAL JUDGE for {instrument} for the next 15 minutes.

You must produce:
1) detailed English reasoning, referencing evidence and current positions
2) structured signals (entry and/or exit) that can be executed later when conditions match.

AGGREGATED SUMMARY:
{json.dumps(aggregated, ensure_ascii=False)[:4000]}

CURRENT POSITIONS:
{pos_block}

AGENT REPORTS:
{agent_block}

Respond in JSON ONLY:
{{
  \"final_decision\": \"BUY|SELL|HOLD|CLOSE_LONG|CLOSE_SHORT|SCALE_IN|SCALE_OUT|REVERSE\",
  \"confidence\": 0.0-1.0,
  \"reasoning\": \"Detailed English reasoning\",
  \"valid_for_minutes\": 15,
  \"signals\": [
    {{
      \"signal_type\": \"ENTRY|EXIT\",
      \"action\": \"BUY|SELL|CLOSE_LONG|CLOSE_SHORT|SCALE_IN|SCALE_OUT|REVERSE\",
      \"execution_mode\": \"CONDITIONAL|IMMEDIATE\",
      \"position_size\": 0.1-5.0,
      \"confidence\": 0.0-1.0,
      \"entry_price\": number|null,
      \"stop_loss\": number|null,
      \"take_profit\": number|null,
      \"conditions\": [
        {{\"indicator\":\"current_price|rsi_14|macd|...\",\"operator\":\">|<|>=|<=|crosses_above|crosses_below\",\"threshold\": number}}
      ],
      \"rationale\": \"Short English rationale\"
    }}
  ]
}}
"""

        try:
            from genai_module.contracts import LLMRequest
            req = LLMRequest(prompt=prompt, temperature=0.1, max_tokens=1200, model=None)
            resp = await self.llm_client.generate(req)
            content = getattr(resp, "content", None) or getattr(resp, "text", None) or str(resp)
            parsed = json.loads(content)
            final_decision = (parsed.get("final_decision") or parsed.get("decision") or "HOLD").upper()
            confidence = float(parsed.get("confidence", aggregated.get("confidence", 0.0)))
            reasoning = parsed.get("reasoning", aggregated.get("reasoning", ""))
            signals = parsed.get("signals", []) if isinstance(parsed.get("signals", []), list) else []

            # Decision returned to engine stays in BUY/SELL/HOLD family; signals carry richer actions
            decision_for_engine = final_decision
            if final_decision in {"CLOSE_LONG", "SCALE_OUT"}:
                decision_for_engine = "SELL"
            elif final_decision == "CLOSE_SHORT":
                decision_for_engine = "BUY"
            elif final_decision == "REVERSE":
                decision_for_engine = "HOLD"

            return {
                "decision": decision_for_engine,
                "confidence": confidence,
                "reasoning": reasoning,
                "details": {
                    "judge": parsed,
                    "signals": signals,
                    "valid_for_minutes": parsed.get("valid_for_minutes", 15),
                    "positions": positions,
                    "aggregated_analysis": aggregated.get("aggregated_analysis", aggregated),
                }
            }
        except Exception as e:
            logger.warning(f"Judge decision failed, using aggregate fallback: {e}")
            return aggregated

    async def _on_signal_triggered(self, event: SignalTriggerEvent) -> None:
        """Execute a triggered signal through the mode-aware execution adapter."""
        # Safety switches
        dry_run = bool(self.config.get("auto_execute_dry_run", False))

        try:
            from .signal_creator import mark_signal_status
        except Exception:
            mark_signal_status = None

        if dry_run:
            if mark_signal_status:
                try:
                    await mark_signal_status(event.condition_id, "executed", mongo_db=self.mongo_db, extra={"dry_run": True})
                except Exception:
                    pass
            return

        try:
            res = await self.execution_adapter.execute_trading_decision(
                instrument=event.instrument,
                decision=event.action,
                confidence=float(event.confidence or 0.0),
                analysis_details={
                    "current_price": float(event.current_price or 0.0),
                    "entry_price": float(event.current_price or 0.0),
                    "quantity": max(1, int(round(float(event.position_size or 1.0)))),
                    "stop_loss": event.stop_loss,
                    "take_profit": event.take_profit,
                    "signal_id": event.condition_id,
                },
                position_manager=self.position_manager,
            )
            if mark_signal_status:
                try:
                    await mark_signal_status(event.condition_id, "executed", mongo_db=self.mongo_db, extra={"execution_result": res})
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"EnhancedTradingOrchestrator auto-execute failed: {e}", exc_info=True)

    async def _get_technical_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get technical indicators for analysis."""
        if self.technical_data_provider:
            return await self.technical_data_provider.get_indicators(
                context.get("instrument", "BANKNIFTY")
            )
        return {}

    async def _get_ohlc_data(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get OHLC data for analysis (needed by TechnicalAgent, VolumeAgent, etc.)."""
        if self.market_data_provider:
            return await self.market_data_provider.get_ohlc_data(
                context.get("instrument", "BANKNIFTY"), periods=100
            )
        return []

    async def _get_news_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get news and sentiment data for analysis (needed by SentimentAgent)."""
        if self.news_data_provider:
            return await self.news_data_provider.get_news_data(
                context.get("instrument", "BANKNIFTY")
            )
        return {}

    async def _get_fundamental_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get fundamental data for analysis (needed by FundamentalAgent)."""
        if self.fundamental_data_provider:
            return await self.fundamental_data_provider.get_fundamental_data(
                context.get("instrument", "BANKNIFTY")
            )
        return {}

    async def _get_macro_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get macroeconomic data for analysis (needed by MacroAgent)."""
        if self.macro_data_provider:
            return await self.macro_data_provider.get_macro_data()
        return {}

    async def _run_agents(self, context: Dict[str, Any], technical_data: Dict[str, Any],
                         ohlc_data: List[Dict[str, Any]] = None,
                         news_data: Dict[str, Any] = None,
                         fundamental_data: Dict[str, Any] = None,
                         macro_data: Dict[str, Any] = None) -> List[AnalysisResult]:
        """Run all agents concurrently."""
        # Prepare context for agents
        agent_context = context.copy()
        agent_context["technical_indicators"] = technical_data

        # Add OHLC data if available
        if ohlc_data:
            agent_context["ohlc"] = ohlc_data

        # Add news/sentiment data if available
        if news_data:
            agent_context.update(news_data)

        # Add fundamental data if available
        if fundamental_data:
            agent_context.update(fundamental_data)

        # Add macro data if available
        if macro_data:
            agent_context.update(macro_data)

        # Run agents concurrently
        tasks = []
        for agent in self.agents:
            task = asyncio.create_task(self._run_single_agent(agent, agent_context))
            tasks.append(task)

        # Wait for all agents to complete
        agent_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and return valid results
        valid_results = []
        for i, result in enumerate(agent_results):
            if isinstance(result, Exception):
                logger.warning(f"Agent {self.agents[i].__class__.__name__} failed: {result}")
                continue
            valid_results.append(result)

        return valid_results

    async def _run_single_agent(self, agent: Any, context: Dict[str, Any]) -> AnalysisResult:
        """Run a single agent with proper error handling."""
        try:
            if hasattr(agent, 'analyze'):
                result = await agent.analyze(context)
                # Ensure result has agent identifier
                agent_name = agent.__class__.__name__
                if hasattr(result, 'agent'):
                    result.agent = agent_name

                if hasattr(result, 'details') and result.details is not None:
                    if isinstance(result.details, dict):
                        result.details['agent'] = agent_name
                        # Convert numpy types to Python types for JSON serialization
                        result.details = convert_numpy_types(result.details)
                return result
            else:
                logger.warning(f"Agent {agent.__class__.__name__} does not have analyze method")
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"error": "No analyze method", "agent": agent.__class__.__name__},
                    agent=agent.__class__.__name__
                )
        except Exception as e:
            logger.warning(f"Agent {agent.__class__.__name__} failed: {e}")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"error": str(e), "agent": agent.__class__.__name__},
                agent=agent.__class__.__name__
            )

    async def _aggregate_decisions(self, agent_results: List[AnalysisResult]) -> Dict[str, Any]:
        """Aggregate agent results into final trading decision."""
        if not agent_results:
            return {
                "decision": "HOLD",
                "confidence": 0.0,
                "reasoning": "No agent results available"
            }

        # Simple voting system for now
        buy_votes = 0
        sell_votes = 0
        hold_votes = 0
        total_confidence = 0.0
        reasonings = []
        key_insights = []

        for result in agent_results:
            confidence = getattr(result, 'confidence', 0.0)
            decision = getattr(result, 'decision', 'HOLD').upper()
            agent_name = getattr(result, 'agent', 'Unknown')

            total_confidence += confidence

            if 'BUY' in decision:
                buy_votes += 1
            elif 'SELL' in decision:
                sell_votes += 1
            else:
                hold_votes += 1

            # Collect reasoning
            agent_reasoning = f"{agent_name}: {decision} ({confidence:.2f})"
            
            # Add detailed reasoning from agent details if available
            if hasattr(result, 'details') and result.details and isinstance(result.details, dict):
                detailed_reasoning = result.details.get('reasoning')
                if detailed_reasoning and len(detailed_reasoning) > 10:  # Only if substantial
                    agent_reasoning += f" - {detailed_reasoning[:200]}..." if len(detailed_reasoning) > 200 else f" - {detailed_reasoning}"
            
            reasonings.append(agent_reasoning)
            
            # Simple key insights from agents with high confidence
            if confidence > 0.7 and decision != "HOLD":
                key_insights.append(f"{agent_name} suggests {decision} with {confidence:.0%} confidence")

        # Determine final decision
        if buy_votes > sell_votes:
            final_decision = "BUY"
        elif sell_votes > buy_votes:
            final_decision = "SELL"
        else:
            final_decision = "HOLD"

        avg_confidence = total_confidence / len(agent_results) if agent_results else 0.0
        
        # Basic risk assessment based on consensus
        risk_assessment = "LOW"
        if final_decision != "HOLD":
            if avg_confidence < 0.4:
                risk_assessment = "HIGH"
            elif avg_confidence < 0.6:
                risk_assessment = "MEDIUM"

        return {
            "decision": final_decision,
            "confidence": avg_confidence,
            "reasoning": " | ".join(reasonings),
            "agent_results": agent_results,
            "aggregated_analysis": {
                "consensus_direction": final_decision,
                "confidence_score": avg_confidence,
                "risk_assessment": risk_assessment,
                "key_insights": key_insights,
                "agent_breakdown": {
                    "buy_signals": buy_votes,
                    "sell_signals": sell_votes,
                    "hold_signals": hold_votes,
                    "total_agents": len(agent_results)
                }
            }
        }

    async def _execute_decision(self, decision: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute the trading decision using the appropriate adapter."""
        instrument = context.get("instrument", "UNKNOWN")

        # Only execute if confidence is above threshold and not HOLD
        if decision.get("confidence", 0.0) < 0.6 or decision.get("decision") == "HOLD":
            logger.debug(f"Skipping execution: low confidence or HOLD decision")
            return None

        # Execute via adapter
        execution_result = await self.execution_adapter.execute_trading_decision(
            instrument=instrument,
            decision=decision["decision"],
            confidence=decision["confidence"],
            analysis_details=context,
            position_manager=self.position_manager
        )

        return execution_result

    async def finalize_backtest(self):
        """Finalize backtest if in BACKTEST mode."""
        if self.context.mode == "BACKTEST" and hasattr(self.execution_adapter, 'finalize_backtest'):
            await self.execution_adapter.finalize_backtest()

    def get_mode(self) -> str:
        """Get current execution mode."""
        return self.context.mode

    def get_run_id(self) -> Optional[str]:
        """Get current run ID."""
        return self.context.run_id

    async def _publish_agent_results(self, agent_results: List[AnalysisResult], context: Dict[str, Any]) -> None:
        """Publish individual agent results to WebSocket for UI."""
        if not self.redis_client:
            return

        try:
            instrument = context.get("instrument", self.context.instrument)

            for result in agent_results:
                # Use result.agent if set, otherwise fallback to details['agent'], finally 'unknown'
                agent_name = getattr(result, 'agent', None)
                if not agent_name and hasattr(result, 'details') and result.details:
                    agent_name = result.details.get('agent')
                if not agent_name:
                    agent_name = 'unknown'

                agent_data = {
                    "agent_name": agent_name,
                    "decision": getattr(result, 'decision', 'HOLD'),
                    "confidence": float(getattr(result, 'confidence', 0.0)),
                    "timestamp": datetime.now(IST).isoformat(),
                    "instrument": instrument,
                    "details": self._json_safe_dict(getattr(result, 'details', {})),
                    "reasoning": getattr(result, 'details', {}).get('reasoning', ''),
                    "technical_indicators": self._json_safe_dict(getattr(result, 'details', {}).get('technical_indicators', {})),
                    "cycle_info": self._json_safe_dict(context.get('cycle_info', {})),
                    "mode": self.context.mode,
                    "run_id": self.context.run_id
                }

                # Publish to general and instrument-specific channels
                self.redis_client.publish("engine:decision", json.dumps(agent_data))
                self.redis_client.publish(f"engine:decision:{instrument}", json.dumps(agent_data))

                logger.debug(f"Published agent analysis for {agent_data['agent_name']}: {agent_data['decision']} ({agent_data['confidence']:.2f})")

        except Exception as e:
            logger.warning(f"Failed to publish agent results to WebSocket: {e}")

    def _json_safe_dict(self, data: Any) -> Any:
        """Convert data to JSON-safe format, handling numpy types."""
        if isinstance(data, dict):
            return {k: self._json_safe_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._json_safe_dict(item) for item in data]
        elif hasattr(data, 'item'):  # numpy types
            return data.item()
        elif isinstance(data, (int, float, str, bool)) or data is None:
            return data
        else:
            # Convert to string for unknown types
            return str(data)

    async def _publish_final_decision(self, decision: Dict[str, Any], agent_results: List[AnalysisResult], context: Dict[str, Any]) -> None:
        """Publish final orchestrator decision to WebSocket for UI."""
        if not self.redis_client:
            logger.warning("No Redis client available for publishing final decision")
            return


        try:
            instrument = context.get("instrument", self.context.instrument)

            agent_responses = [
                {
                    "agent": getattr(result, 'agent', 'unknown'),
                    "decision": getattr(result, 'decision', 'HOLD'),
                    "confidence": float(getattr(result, 'confidence', 0.0)),
                    "excluded": getattr(result, 'excluded', False),
                    "exclusion_reason": getattr(result, 'exclusion_reason', None),
                    "details": getattr(result, 'details', {})
                } for result in agent_results
            ]

            decision_data = {
                "instrument": instrument,
                "final_decision": decision.get("decision", "HOLD"),
                "confidence": float(decision.get("confidence", 0.0)),
                "reasoning": decision.get("reasoning", ""),
                "timestamp": datetime.now(IST).isoformat(),
                "agent_responses": agent_responses,
                "mode": self.context.mode,
                "run_id": self.context.run_id,
                "details": {
                    "aggregated_analysis": decision.get("aggregated_analysis", {})
                }
            }


            # Publish to orchestrator decision channels (separate from agent channels)
            self.redis_client.publish("engine:orchestrator_decision", json.dumps(decision_data))
            self.redis_client.publish(f"engine:orchestrator_decision:{instrument}", json.dumps(decision_data))

            # Persist last decision in Redis for "replay on subscribe"
            # Publish to Redis with run isolation
            from .system_context import get_cache_manager
            cache_manager = get_cache_manager()
            cache_manager.set(f"engine:orchestrator_decision:{instrument}:latest", json.dumps(decision_data), expire_seconds=3600)  # 1 hour
            cache_manager.set("engine:orchestrator_decision:latest", json.dumps(decision_data), expire_seconds=3600)

            logger.debug(f"Published orchestrator decision: {decision_data['final_decision']} ({decision_data['confidence']:.2f}) for {instrument}")

        except Exception as e:
            logger.warning(f"Failed to publish final decision to WebSocket: {e}")