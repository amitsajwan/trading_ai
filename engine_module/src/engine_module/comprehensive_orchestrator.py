"""Comprehensive Trading Orchestrator with All Enhancements.

This orchestrator integrates:
- Regime detection
- Multi-timeframe analysis
- Spread strategies
- Enhanced agents (Research Manager, Momentum, Risk)
- Formal debate protocol
- Structured reports
- Risk management
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from datetime import datetime, timedelta
from dataclasses import dataclass

from .contracts import AnalysisResult, Orchestrator, TechnicalDataProvider, PositionManagerProvider

# Enhanced agents
from .agents.enhanced_momentum_agent import EnhancedMomentumAgent
from .agents.enhanced_research_manager import EnhancedResearchManager
from .agents.enhanced_risk_agents import EnhancedRiskAgent

# Analysis tools
from .analysis.regime_detector import RegimeDetector, MarketRegime
from .analysis.multi_timeframe import MultiTimeframeAnalyzer

# Strategies
from .strategies.iron_condor import IronCondorStrategy
# Note: credit_spreads.py has misnamed classes:
# - BullCallSpreadStrategy is actually BullPutSpreadStrategy
# - BearPutSpreadStrategy is actually BearCallSpreadStrategy  
from .strategies.credit_spreads import BullCallSpreadStrategy as BullPutSpreadStrategy, BearPutSpreadStrategy as BearCallSpreadStrategy
from .strategies.debit_spreads import BullCallSpreadStrategy as BullCallSpreadDebitStrategy, BearPutSpreadStrategy

# Communication
from .communication import StructuredReport, ReportType, ReportPriority

logger = logging.getLogger(__name__)


@runtime_checkable
class MarketDataProvider(Protocol):
    """Protocol for market data providers."""
    async def get_ohlc_data(self, symbol: str, periods: int = 100) -> List[Dict[str, Any]]:
        """Get OHLC data for symbol."""
        ...


class ComprehensiveTradingOrchestrator(Orchestrator):
    """Comprehensive orchestrator with all enhancements integrated.
    
    This orchestrator coordinates:
    1. Regime detection
    2. Multi-timeframe analysis
    3. Enhanced agent analysis (with structured reports)
    4. Formal debates (Research Manager)
    5. Risk deliberation
    6. Strategy selection and execution
    """
    
    def __init__(self,
                 market_data_provider: MarketDataProvider,
                 technical_data_provider: Optional[TechnicalDataProvider] = None,
                 position_provider: Optional[PositionManagerProvider] = None,
                 multi_timeframe_reader: Optional[Any] = None,
                 options_chain_provider: Optional[Any] = None,
                 config: Optional[Dict[str, Any]] = None):
        """Initialize comprehensive trading orchestrator.
        
        Args:
            market_data_provider: Provider for market data
            technical_data_provider: Provider for technical indicators
            position_provider: Optional provider for current positions
            multi_timeframe_reader: Optional multi-timeframe data reader
            options_chain_provider: Optional options chain provider
            config: Configuration dictionary
        """
        self.market_data_provider = market_data_provider
        self.technical_data_provider = technical_data_provider
        self.position_provider = position_provider
        self.multi_timeframe_reader = multi_timeframe_reader
        self.options_chain_provider = options_chain_provider
        self.config = config or self._get_default_config()
        
        # Initialize regime detector
        self.regime_detector = RegimeDetector(self.config.get('regime_config', {}))
        
        # Initialize multi-timeframe analyzer
        self.multi_timeframe_analyzer = MultiTimeframeAnalyzer(
            self.config.get('multi_timeframe_config', {})
        )
        
        # Initialize enhanced agents
        self.agents = self._initialize_enhanced_agents()
        
        # Initialize spread strategies
        self.spread_strategies = self._initialize_spread_strategies()
        
        # Trading state
        self.symbol = self.config.get('symbol', 'BANKNIFTY')
        self.last_cycle_time = None
        self.cycle_count = 0
        
        logger.info(f"Comprehensive Trading Orchestrator initialized for {self.symbol}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'symbol': 'BANKNIFTY',
            'cycle_interval_minutes': 15,
            'min_confidence_threshold': 0.6,
            'max_agents_per_cycle': 5,
            'risk_per_trade_pct': 1.0,
            'position_size_pct': 5.0,
            'max_positions': 3,
            'regime_config': {
                'adx_trending': 25,
                'iv_high_percentile': 80,
                'iv_low_percentile': 20
            },
            'multi_timeframe_config': {
                'timeframes': ['5m', '15m', '1h', 'daily']
            },
            'agents': {
                'momentum': {'enabled': True},
                'research_manager': {'enabled': True},
                'risk': {'enabled': True}
            },
            'strategies': {
                'iron_condor': {'enabled': True},
                'credit_spreads': {'enabled': True},
                'debit_spreads': {'enabled': True}
            }
        }
    
    def _initialize_enhanced_agents(self) -> Dict[str, Any]:
        """Initialize enhanced agents."""
        agents = {}
        
        # Enhanced Momentum Agent
        if self.config.get('agents', {}).get('momentum', {}).get('enabled', True):
            agents['momentum'] = EnhancedMomentumAgent(
                self.config.get('momentum_config', {})
            )
        
        # Enhanced Research Manager
        if self.config.get('agents', {}).get('research_manager', {}).get('enabled', True):
            agents['research_manager'] = EnhancedResearchManager(
                llm_client=None,  # Can be injected if available
                config=self.config.get('research_manager_config', {})
            )
        
        # Enhanced Risk Agent
        if self.config.get('agents', {}).get('risk', {}).get('enabled', True):
            agents['risk'] = EnhancedRiskAgent(
                self.config.get('risk_config', {})
            )
        
        logger.info(f"Initialized {len(agents)} enhanced agents: {list(agents.keys())}")
        return agents
    
    def _initialize_spread_strategies(self) -> Dict[str, Any]:
        """Initialize spread strategies."""
        strategies = {}
        strategy_config = self.config.get('strategies', {})
        
        if strategy_config.get('iron_condor', {}).get('enabled', True):
            strategies['iron_condor'] = IronCondorStrategy(
                self.config.get('iron_condor_config', {})
            )
        
        if strategy_config.get('credit_spreads', {}).get('enabled', True):
            strategies['bull_put_spread'] = BullPutSpreadStrategy(
                self.config.get('credit_spread_config', {})
            )
            strategies['bear_call_spread'] = BearCallSpreadStrategy(
                self.config.get('credit_spread_config', {})
            )
        
        if strategy_config.get('debit_spreads', {}).get('enabled', True):
            strategies['bull_call_spread'] = BullCallSpreadDebitStrategy(
                self.config.get('debit_spread_config', {})
            )
            strategies['bear_put_spread'] = BearPutSpreadStrategy(
                self.config.get('debit_spread_config', {})
            )
        
        logger.info(f"Initialized {len(strategies)} spread strategies: {list(strategies.keys())}")
        return strategies
    
    async def run_cycle(self, context: Dict[str, Any]) -> AnalysisResult:
        """Run one comprehensive trading cycle.
        
        Cycle steps:
        1. Fetch market data and multi-timeframe data
        2. Detect market regime
        3. Perform multi-timeframe analysis
        4. Run enhanced agents (with structured reports)
        5. Conduct formal debates (if Research Manager enabled)
        6. Risk deliberation
        7. Select and build spread strategies (based on regime)
        8. Synthesize final decision
        
        Args:
            context: Trading context with symbol, market data, etc.
        
        Returns:
            AnalysisResult with comprehensive trading decision
        """
        self.cycle_count += 1
        cycle_start = datetime.now()
        
        try:
            logger.info(f"Starting comprehensive trading cycle #{self.cycle_count} at {cycle_start.strftime('%H:%M:%S')}")
            
            # Step 1: Get market data
            symbol = context.get('symbol', self.symbol)
            market_data = await self.market_data_provider.get_ohlc_data(symbol, periods=100)
            
            if not market_data:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "NO_MARKET_DATA", "cycle": self.cycle_count}
                )
            
            current_price = market_data[-1].get('close', 0) if market_data else 0
            
            # Step 2: Get multi-timeframe data
            multi_timeframe_data = {}
            if self.multi_timeframe_reader:
                try:
                    multi_timeframe_data = await self._fetch_multi_timeframe_data(symbol)
                except Exception as e:
                    logger.warning(f"Failed to fetch multi-timeframe data: {e}")
            
            # Step 3: Get technical indicators
            technical_indicators = {}
            if self.technical_data_provider:
                try:
                    tech_data = await self.technical_data_provider.get_technical_indicators(symbol, periods=100)
                    technical_indicators = tech_data.to_dict() if hasattr(tech_data, 'to_dict') else tech_data
                except Exception as e:
                    logger.warning(f"Failed to fetch technical indicators: {e}")
            
            # Step 4: Detect market regime
            regime = None
            regime_result = None
            try:
                regime_result = self.regime_detector.detect({
                    'close': current_price,
                    'sma_20': technical_indicators.get('sma_20', 0),
                    'ema_50': technical_indicators.get('ema_50', 0),
                    'adx': technical_indicators.get('adx', 0),
                    'iv_percentile': technical_indicators.get('iv_percentile', 50),
                    'volume_ratio': technical_indicators.get('volume_ratio', 1.0),
                    'bollinger_upper': technical_indicators.get('bollinger_upper', current_price * 1.02),
                    'bollinger_lower': technical_indicators.get('bollinger_lower', current_price * 0.98)
                })
                regime = regime_result.value if hasattr(regime_result, 'value') else str(regime_result)
                logger.info(f"Detected market regime: {regime}")
            except Exception as e:
                logger.warning(f"Failed to detect regime: {e}")
            
            # Step 5: Multi-timeframe analysis
            mtf_analysis = None
            if multi_timeframe_data:
                try:
                    mtf_analysis = self.multi_timeframe_analyzer.analyze(multi_timeframe_data)
                    # Convert MultiTimeframeAnalysis dataclass to dict-like access
                    dominant_trend = mtf_analysis.dominant_trend if hasattr(mtf_analysis, 'dominant_trend') else None
                    if hasattr(dominant_trend, 'value'):
                        dominant_trend = dominant_trend.value
                    logger.debug(f"Multi-timeframe analysis: {dominant_trend}")
                except Exception as e:
                    logger.warning(f"Failed multi-timeframe analysis: {e}")
            
            # Step 6: Get current positions
            current_positions = []
            if self.position_provider:
                try:
                    all_positions = await self.position_provider.get_positions(symbol=symbol)
                    current_positions = [
                        pos for pos in all_positions
                        if pos.get('status', 'active') == 'active' and pos.get('symbol') == symbol
                    ]
                except Exception as e:
                    logger.warning(f"Failed to fetch positions: {e}")
            
            # Step 7: Prepare enhanced context for agents
            enhanced_context = {
                'market_data': {
                    'close': current_price,
                    'open': market_data[-1].get('open', current_price) if market_data else current_price,
                    'high': market_data[-1].get('high', current_price) if market_data else current_price,
                    'low': market_data[-1].get('low', current_price) if market_data else current_price,
                    'volume': market_data[-1].get('volume', 0) if market_data else 0,
                    'instrument': symbol,
                    **technical_indicators
                },
                'multi_timeframe': multi_timeframe_data,
                'regime': regime,
                'current_positions': current_positions,
                'technical_indicators': technical_indicators,
                'symbol': symbol,
                'timestamp': cycle_start
            }
            
            # Step 8: Run enhanced agents
            agent_results = await self._run_enhanced_agents(enhanced_context)
            
            # Step 9: Risk deliberation
            risk_result = None
            if 'risk' in self.agents and 'risk' in agent_results:
                risk_result = agent_results['risk']
                if risk_result.decision == "VETO":
                    logger.warning("Risk agent vetoed trade")
                    return AnalysisResult(
                        decision="HOLD",
                        confidence=0.0,
                        details={
                            "reason": "RISK_VETO",
                            "risk_details": risk_result.details,
                            "cycle": self.cycle_count
                        }
                    )
            
            # Step 10: Select and build strategies based on regime
            strategy_decision = await self._select_and_build_strategy(
                regime, current_price, technical_indicators, enhanced_context
            )
            
            # Step 11: Synthesize final decision
            final_decision = await self._synthesize_decision(
                agent_results, strategy_decision, risk_result, regime, mtf_analysis
            )
            
            # Update cycle timing
            self.last_cycle_time = cycle_start
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(f"Trading cycle #{self.cycle_count} completed in {cycle_duration:.2f}s: {final_decision.decision}")
            
            # Add cycle info to details
            details = final_decision.details or {}
            details['cycle_info'] = {
                'cycle_number': self.cycle_count,
                'duration_seconds': cycle_duration,
                'regime': regime,
                'dominant_trend': str(mtf_analysis.dominant_trend.value) if mtf_analysis and hasattr(mtf_analysis, 'dominant_trend') and mtf_analysis.dominant_trend else None,
                'confluence_score': mtf_analysis.confluence_score if mtf_analysis and hasattr(mtf_analysis, 'confluence_score') else None
            }
            
            return AnalysisResult(
                decision=final_decision.decision,
                confidence=final_decision.confidence,
                details=details,
                agent="ComprehensiveOrchestrator"
            )
        
        except Exception as e:
            logger.exception(f"Error in comprehensive trading cycle #{self.cycle_count}")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"reason": f"CYCLE_ERROR: {str(e)}", "cycle": self.cycle_count},
                agent="ComprehensiveOrchestrator"
            )
    
    async def _fetch_multi_timeframe_data(self, symbol: str) -> Dict[str, Dict[str, Any]]:
        """Fetch multi-timeframe data."""
        if not self.multi_timeframe_reader:
            return {}
        
        try:
            timeframes = ['5m', '15m', '1h', 'daily']
            mtf_data = {}
            
            for tf in timeframes:
                data = await self.multi_timeframe_reader.fetch_ohlc(symbol, tf, limit=100)
                if data:
                    mtf_data[tf] = {
                        'close': data[-1].get('close', 0) if data else 0,
                        'sma_20': data[-1].get('sma_20', 0) if data else 0,
                        'ema_50': data[-1].get('ema_50', 0) if data else 0,
                        'rsi': data[-1].get('rsi', 50) if data else 50,
                        'macd': data[-1].get('macd', 0) if data else 0,
                        'macd_signal': data[-1].get('macd_signal', 0) if data else 0,
                        'adx': data[-1].get('adx', 0) if data else 0
                    }
            
            return mtf_data
        except Exception as e:
            logger.warning(f"Failed to fetch multi-timeframe data: {e}")
            return {}
    
    async def _run_enhanced_agents(self, context: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """Run all enhanced agents with structured reporting."""
        agent_results = {}
        
        # Run agents concurrently
        tasks = []
        for agent_name, agent in self.agents.items():
            task = asyncio.create_task(
                self._run_single_agent(agent_name, agent, context)
            )
            tasks.append(task)
        
        # Wait for all agents
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, (agent_name, _) in enumerate(self.agents.items()):
            if i < len(results):
                result = results[i]
                if isinstance(result, Exception):
                    logger.error(f"Agent {agent_name} failed: {result}")
                    agent_results[agent_name] = AnalysisResult(
                        decision="HOLD",
                        confidence=0.0,
                        details={"reason": f"AGENT_ERROR: {str(result)}"}
                    )
                else:
                    agent_results[agent_name] = result
        
        return agent_results
    
    async def _run_single_agent(self, agent_name: str, agent: Any, context: Dict[str, Any]) -> AnalysisResult:
        """Run a single enhanced agent."""
        try:
            return await agent.analyze(context)
        except Exception as e:
            logger.exception(f"Error in agent {agent_name}")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"reason": f"AGENT_ERROR: {str(e)}", "agent": agent_name}
            )
    
    async def _select_and_build_strategy(
        self,
        regime: Optional[str],
        current_price: float,
        technical_indicators: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Select and build spread strategy based on regime."""
        if not regime or not self.spread_strategies:
            return None
        
        # Get options chain if available
        if not self.options_chain_provider:
            return None
        
        try:
            # Get suitable strategies for regime
            try:
                if hasattr(self.regime_detector, 'get_suitable_strategies'):
                    regime_enum = None
                    for mr in MarketRegime:
                        if mr.value == regime or mr.name.lower() == regime.lower():
                            regime_enum = mr
                            break
                    if regime_enum:
                        suitable_strategies = self.regime_detector.get_suitable_strategies(regime_enum)
                    else:
                        suitable_strategies = ['iron_condor']
                else:
                    suitable_strategies = ['iron_condor']
            except Exception:
                # Fallback mapping
                suitable_strategies = {
                    'ranging': ['iron_condor', 'bull_put_spread', 'bear_call_spread'],
                    'trending_up': ['bull_call_spread', 'bull_put_spread'],
                    'trending_down': ['bear_put_spread', 'bear_call_spread'],
                    'high_volatility': ['iron_condor']
                }.get(regime, ['iron_condor'])
            
            # Try to build strategy
            for strategy_name in suitable_strategies:
                if strategy_name in self.spread_strategies:
                    strategy = self.spread_strategies[strategy_name]
                    
                    # Fetch options chain
                    option_chain = await self._fetch_options_chain(context.get('symbol', self.symbol))
                    if not option_chain:
                        continue
                    
                    # Build spread
                    legs = strategy.build_spread(current_price, option_chain)
                    if legs:
                        metrics = strategy.calculate_metrics(legs)
                        
                        # Validate spread
                        if strategy.validate_spread(legs, metrics):
                            return {
                                'strategy_name': strategy_name,
                                'legs': legs,
                                'metrics': metrics,
                                'confidence': 0.7  # Base confidence for spread
                            }
        
        except Exception as e:
            logger.warning(f"Failed to build strategy: {e}")
        
        return None
    
    async def _fetch_options_chain(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch options chain data."""
        if not self.options_chain_provider:
            return None
        
        try:
            # Assuming options chain provider has a fetch method
            chain = await self.options_chain_provider.fetch_chain(symbol)
            return chain
        except Exception as e:
            logger.warning(f"Failed to fetch options chain: {e}")
            return None
    
    async def _synthesize_decision(
        self,
        agent_results: Dict[str, AnalysisResult],
        strategy_decision: Optional[Dict[str, Any]],
        risk_result: Optional[AnalysisResult],
        regime: Optional[str],
        mtf_analysis: Optional[Dict[str, Any]]
    ) -> AnalysisResult:
        """Synthesize final decision from all inputs."""
        # Collect decisions and confidences
        decisions = []
        confidences = []
        reasoning_parts = []
        
        # Add agent decisions
        for agent_name, result in agent_results.items():
            if result.decision != "HOLD":
                decisions.append(result.decision)
                confidences.append(result.confidence)
                if result.details and 'reasoning' in result.details:
                    reasoning_parts.append(f"{agent_name}: {result.details['reasoning']}")
                elif result.details and 'summary' in result.details:
                    reasoning_parts.append(f"{agent_name}: {result.details['summary']}")
        
        # Add strategy decision if available
        if strategy_decision:
            decisions.append(strategy_decision['strategy_name'].upper())
            confidences.append(strategy_decision['confidence'])
            reasoning_parts.append(f"Spread strategy: {strategy_decision['strategy_name']}")
        
        # Determine final decision
        if not decisions:
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={
                    "reasoning": "No clear signals from agents",
                    "regime": regime,
                    "agent_results": {name: {"decision": r.decision, "confidence": r.confidence}
                                     for name, r in agent_results.items()}
                },
                agent="ComprehensiveOrchestrator"
            )
        
        # Use highest confidence decision
        best_idx = confidences.index(max(confidences))
        final_decision = decisions[best_idx]
        final_confidence = confidences[best_idx]
        
        # Build details
        details = {
            "reasoning": " | ".join(reasoning_parts[:3]),  # Top 3 reasons
            "regime": regime,
            "dominant_trend": str(mtf_analysis.dominant_trend.value) if mtf_analysis and hasattr(mtf_analysis, 'dominant_trend') and mtf_analysis.dominant_trend else None,
            "agent_results": {name: {"decision": r.decision, "confidence": r.confidence}
                             for name, r in agent_results.items()}
        }
        
        if strategy_decision:
            details['strategy'] = strategy_decision
        
        return AnalysisResult(
            decision=final_decision,
            confidence=final_confidence,
            details=details,
            agent="ComprehensiveOrchestrator"
        )
    
    def get_cycle_stats(self) -> Dict[str, Any]:
        """Get statistics about completed cycles."""
        return {
            'total_cycles': self.cycle_count,
            'last_cycle_time': self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            'symbol': self.symbol,
            'active_agents': list(self.agents.keys()),
            'active_strategies': list(self.spread_strategies.keys()),
            'config': self.config
        }
