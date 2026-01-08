"""Enhanced 15-minute cycle orchestrator implementing trading engine contracts.

This orchestrator runs 15-minute trading cycles with multiple specialized agents,
aggregating signals with confidence voting for systematic trading decisions.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from datetime import datetime, timedelta
from dataclasses import dataclass

from .contracts import AnalysisResult, Orchestrator, TechnicalDataProvider, PositionManagerProvider
from .agents.momentum_agent import MomentumAgent
from .agents.trend_agent import TrendAgent
from .agents.mean_reversion_agent import MeanReversionAgent
from .agents.volume_agent import VolumeAgent

logger = logging.getLogger(__name__)


@dataclass
class TradingDecision:
    """Enhanced trading decision with position management."""
    action: str  # BUY, SELL, HOLD
    confidence: float
    reasoning: str
    entry_price: float
    stop_loss: float
    take_profit: float
    quantity: int
    risk_amount: float
    agent_signals: Dict[str, AnalysisResult]
    timestamp: datetime
    position_action: str = "OPEN_NEW"  # OPEN_NEW, ADD_TO_LONG, ADD_TO_SHORT, CLOSE_LONG, CLOSE_SHORT

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'action': self.action,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'quantity': self.quantity,
            'risk_amount': self.risk_amount,
            'agent_signals': {
                name: {
                    'decision': signal.decision,
                    'confidence': signal.confidence,
                    'details': signal.details
                }
                for name, signal in self.agent_signals.items()
            },
            'timestamp': self.timestamp.isoformat(),
            'position_action': self.position_action
        }


@runtime_checkable
class MarketDataProvider(Protocol):
    """Protocol for market data providers."""
    async def get_ohlc_data(self, symbol: str, periods: int = 100) -> List[Dict[str, Any]]:
        """Get OHLC data for symbol."""
        ...


class PositionProvider(PositionManagerProvider):
    """Protocol for position providers."""
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get current positions.
        
        Args:
            symbol: Optional symbol filter. If None, returns all positions.
            
        Returns:
            List of position dictionaries with keys like:
            - symbol: str
            - action: str (BUY/SELL)
            - quantity: int
            - entry_price: float
            - current_price: float
            - stop_loss: float
            - take_profit: float
            - status: str (active/closed)
            - position_id: str
        """
        ...


    async def execute_trading_decision(self, instrument: str, decision: str, confidence: float, analysis_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a trading decision."""
        ...


class EnhancedTradingOrchestrator(Orchestrator):

    def __init__(self,
                 market_data_provider: MarketDataProvider,
                 technical_data_provider: Optional[TechnicalDataProvider] = None,
                 position_provider: Optional[PositionProvider] = None,
                 config: Dict[str, Any] = None):
        """Initialize enhanced trading orchestrator.

        Args:
            market_data_provider: Provider for market data
            technical_data_provider: Provider for technical indicators
            position_provider: Optional provider for current positions
            config: Configuration dictionary
        """
        self.market_data_provider = market_data_provider
        self.technical_data_provider = technical_data_provider
        self.position_provider = position_provider
        self.config = config or self._get_default_config()

        # Initialize agents
        self.agents = self._initialize_agents()

        # Trading state
        self.symbol = self.config.get('symbol', 'NIFTY50')
        self.last_cycle_time = None
        self.cycle_count = 0

        logger.info(f"Enhanced Trading Orchestrator initialized for {self.symbol}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'symbol': 'NIFTY50',
            'cycle_interval_minutes': 15,
            'min_confidence_threshold': 0.6,
            'max_agents_per_cycle': 4,
            'risk_per_trade_pct': 1.0,
            'position_size_pct': 5.0,
            'max_positions': 3,  # Maximum number of open positions
            'add_to_position_pct': 0.5,  # Percentage of new position size when adding to existing
            'agents': {
                'momentum': {'enabled': True},
                'trend': {'enabled': True},
                'mean_reversion': {'enabled': True},
                'volume': {'enabled': True}
            }
        }

    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize trading agents."""
        agents = {}

        # Momentum Agent
        if self.config.get('agents', {}).get('momentum', {}).get('enabled', True):
            agents['momentum'] = MomentumAgent(self.config.get('momentum_config', {}))

        # Trend Agent
        if self.config.get('agents', {}).get('trend', {}).get('enabled', True):
            agents['trend'] = TrendAgent(self.config.get('trend_config', {}))

        # Mean Reversion Agent
        if self.config.get('agents', {}).get('mean_reversion', {}).get('enabled', True):
            agents['mean_reversion'] = MeanReversionAgent(self.config.get('mean_reversion_config', {}))

        # Volume Agent
        if self.config.get('agents', {}).get('volume', {}).get('enabled', True):
            agents['volume'] = VolumeAgent(self.config.get('volume_config', {}))

        logger.info(f"Initialized {len(agents)} trading agents: {list(agents.keys())}")
        return agents

    async def run_cycle(self, context: Dict[str, Any]) -> AnalysisResult:
        """Run one 15-minute trading cycle.

        Args:
            context: Trading context (may include symbol, market data, etc.)

        Returns:
            AnalysisResult with aggregated trading decision
        """
        self.cycle_count += 1
        cycle_start = datetime.now()

        try:
            logger.info(f"Starting trading cycle #{self.cycle_count} at {cycle_start.strftime('%H:%M:%S')}")

            # Get market data
            symbol = context.get('symbol', self.symbol)
            market_data = await self.market_data_provider.get_ohlc_data(symbol, periods=100)

            if not market_data:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "NO_MARKET_DATA", "cycle": self.cycle_count}
                )

            # Get current positions for this symbol
            current_positions = []
            if self.position_provider:
                try:
                    all_positions = await self.position_provider.get_positions(symbol=symbol)
                    # Filter for active positions only
                    current_positions = [
                        pos for pos in all_positions 
                        if pos.get('status', 'active') == 'active' and pos.get('symbol') == symbol
                    ]
                    logger.debug(f"Found {len(current_positions)} active positions for {symbol}")
                except Exception as e:
                    logger.warning(f"Failed to fetch positions: {e}")
                    current_positions = []

            # Get technical indicators
            technical_indicators = None
            if self.technical_data_provider:
                try:
                    technical_indicators = await self.technical_data_provider.get_technical_indicators(symbol, periods=100)
                    logger.debug(f"Fetched technical indicators for {symbol}")
                except Exception as e:
                    logger.warning(f"Failed to fetch technical indicators: {e}")

            # Prepare analysis context with position information and technical data
            analysis_context = {
                'ohlc': market_data,
                'symbol': symbol,
                'current_price': market_data[-1].get('close', 0) if market_data else 0,
                'timestamp': cycle_start,
                'current_positions': current_positions,  # Add positions to context
                'has_long_position': any(
                    p.get('action') == 'BUY' and p.get('status') == 'active' 
                    for p in current_positions
                ),
                'has_short_position': any(
                    p.get('action') == 'SELL' and p.get('status') == 'active' 
                    for p in current_positions
                ),
                'position_count': len(current_positions),
                'technical_indicators': technical_indicators.to_dict() if technical_indicators else {}
            }

            # Run all agents
            agent_signals = await self._run_agent_analysis(analysis_context)

            # Aggregate signals with position awareness
            trading_decision = await self._aggregate_signals(
                agent_signals, market_data, current_positions
            )

            # Update cycle timing
            self.last_cycle_time = cycle_start

            # Log cycle completion
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(f"Trading cycle #{self.cycle_count} completed in {cycle_duration:.2f}s")
            # Convert to AnalysisResult format for compatibility
            details = trading_decision.to_dict()
            details['cycle_info'] = {
                'cycle_number': self.cycle_count,
                'duration_seconds': cycle_duration,
                'agents_run': len(agent_signals)
            }

            return AnalysisResult(
                decision=trading_decision.action,
                confidence=trading_decision.confidence,
                details=details
            )

        except Exception as e:
            logger.exception(f"Error in trading cycle #{self.cycle_count}")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"reason": f"CYCLE_ERROR: {str(e)}", "cycle": self.cycle_count}
            )

    async def _run_agent_analysis(self, context: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """Run analysis on all enabled agents."""
        agent_signals = {}

        # Run agents concurrently for better performance
        tasks = []
        for agent_name, agent in self.agents.items():
            task = asyncio.create_task(self._run_single_agent(agent_name, agent, context))
            tasks.append(task)

        # Wait for all agents to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, (agent_name, _) in enumerate(self.agents.items()):
            if i < len(results):
                result = results[i]
                if isinstance(result, Exception):
                    logger.error(f"Agent {agent_name} failed: {result}")
                    agent_signals[agent_name] = AnalysisResult(
                        decision="HOLD",
                        confidence=0.0,
                        details={"reason": f"AGENT_ERROR: {str(result)}"}
                    )
                else:
                    agent_signals[agent_name] = result

        return agent_signals

    async def _run_single_agent(self, agent_name: str, agent: Any, context: Dict[str, Any]) -> AnalysisResult:
        """Run a single agent analysis."""
        try:
            return await agent.analyze(context)
        except Exception as e:
            logger.exception(f"Error in agent {agent_name}")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"reason": f"AGENT_ERROR: {str(e)}", "agent": agent_name}
            )

    async def _aggregate_signals(self,
                                agent_signals: Dict[str, AnalysisResult],
                                market_data: List[Dict[str, Any]],
                                current_positions: List[Dict[str, Any]] = None) -> TradingDecision:
        """Aggregate agent signals into final trading decision."""
        if not agent_signals:
            return TradingDecision(
                action="HOLD",
                confidence=0.0,
                reasoning="No agent signals available",
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                quantity=0,
                risk_amount=0.0,
                agent_signals=agent_signals,
                timestamp=datetime.now(),
                position_action="OPEN_NEW"
            )

        # Count signals by type
        buy_signals = []
        sell_signals = []
        hold_signals = []

        for agent_name, signal in agent_signals.items():
            if signal.decision == "BUY":
                buy_signals.append((agent_name, signal))
            elif signal.decision == "SELL":
                sell_signals.append((agent_name, signal))
            else:
                hold_signals.append((agent_name, signal))

        # Determine consensus
        total_agents = len(agent_signals)
        buy_count = len(buy_signals)
        sell_count = len(sell_signals)

        # Get current price
        current_price = market_data[-1].get('close', 0) if market_data else 0

        # Analyze current positions
        current_positions = current_positions or []
        has_long_position = any(
            p.get('action') == 'BUY' and p.get('status') == 'active' 
            for p in current_positions
        )
        has_short_position = any(
            p.get('action') == 'SELL' and p.get('status') == 'active' 
            for p in current_positions
        )

        # Decision logic with position awareness
        min_confidence = self.config.get('min_confidence_threshold', 0.6)
        max_positions = self.config.get('max_positions', 3)

        # Check if we're at position limit
        if len(current_positions) >= max_positions:
            logger.info(f"At position limit ({len(current_positions)}/{max_positions}), considering exit signals only")
            # Only consider SELL signals if we have long positions, or BUY signals if we have short positions
            if has_long_position and sell_count > 0:
                # Consider closing long positions
                avg_confidence = sum(s.confidence for _, s in sell_signals) / sell_count
                if avg_confidence >= min_confidence:
                    return await self._create_trading_decision(
                        "SELL", avg_confidence, sell_signals, agent_signals, current_price,
                        current_positions, position_action="CLOSE_LONG"
                    )
            elif has_short_position and buy_count > 0:
                # Consider closing short positions
                avg_confidence = sum(s.confidence for _, s in buy_signals) / buy_count
                if avg_confidence >= min_confidence:
                    return await self._create_trading_decision(
                        "BUY", avg_confidence, buy_signals, agent_signals, current_price,
                        current_positions, position_action="CLOSE_SHORT"
                    )
            # At limit and no exit signals - HOLD
            return TradingDecision(
                action="HOLD",
                confidence=0.0,
                reasoning=f"At position limit ({len(current_positions)}/{max_positions}) with no exit signals",
                entry_price=current_price,
                stop_loss=0.0,
                take_profit=0.0,
                quantity=0,
                risk_amount=0.0,
                agent_signals=agent_signals,
                timestamp=datetime.now(),
                position_action="OPEN_NEW"
            )

        if buy_count > sell_count and buy_count >= max(2, total_agents // 2):
            # BUY consensus
            avg_confidence = sum(s.confidence for _, s in buy_signals) / buy_count
            if avg_confidence >= min_confidence:
                # Check if we should add to existing position or open new
                position_action = "ADD_TO_LONG" if has_long_position else "OPEN_NEW"
                return await self._create_trading_decision(
                    "BUY", avg_confidence, buy_signals, agent_signals, current_price,
                    current_positions, position_action=position_action
                )

        elif sell_count > buy_count and sell_count >= max(2, total_agents // 2):
            # SELL consensus
            avg_confidence = sum(s.confidence for _, s in sell_signals) / sell_count
            if avg_confidence >= min_confidence:
                # Check if we should add to existing position or open new
                position_action = "ADD_TO_SHORT" if has_short_position else "OPEN_NEW"
                return await self._create_trading_decision(
                    "SELL", avg_confidence, sell_signals, agent_signals, current_price,
                    current_positions, position_action=position_action
                )

        # No clear consensus - HOLD
        reasoning_parts = []
        if buy_signals:
            reasoning_parts.append(f"{buy_count} BUY signals")
        if sell_signals:
            reasoning_parts.append(f"{sell_count} SELL signals")
        if hold_signals:
            reasoning_parts.append(f"{len(hold_signals)} HOLD signals")

        reasoning = f"No clear consensus: {' | '.join(reasoning_parts)}"

        return TradingDecision(
            action="HOLD",
            confidence=0.0,
            reasoning=reasoning,
            entry_price=current_price,
            stop_loss=0.0,
            take_profit=0.0,
            quantity=0,
            risk_amount=0.0,
            agent_signals=agent_signals,
            timestamp=datetime.now(),
            position_action="OPEN_NEW"
        )

    async def _create_trading_decision(self,
                                      action: str,
                                      confidence: float,
                                      primary_signals: List,
                                      all_signals: Dict[str, AnalysisResult],
                                      current_price: float,
                                      current_positions: List[Dict[str, Any]] = None,
                                      position_action: str = "OPEN_NEW") -> TradingDecision:
        """Create a complete trading decision with position management."""

        # Combine reasoning from primary signals
        reasoning_parts = []
        for agent_name, signal in primary_signals:
            if signal.details and 'reasoning' in signal.details:
                reasoning_parts.extend(signal.details['reasoning'])
            else:
                reasoning_parts.append(f"{agent_name}: {signal.decision}")

        reasoning = " | ".join(reasoning_parts[:3])  # Limit to top 3 reasons

        # Position management from agent details (use first agent's levels)
        primary_agent = primary_signals[0][1]
        agent_details = primary_agent.details or {}

        entry_price = agent_details.get('entry_price', current_price)
        stop_loss = agent_details.get('stop_loss', entry_price * 0.98)
        take_profit = agent_details.get('take_profit', entry_price * 1.04)

        # Calculate quantity based on risk management and position action
        risk_per_trade_pct = self.config.get('risk_per_trade_pct', 1.0)
        account_size = self.config.get('account_size', 100000)
        current_positions = current_positions or []

        # Adjust quantity based on position action
        if position_action in ["ADD_TO_LONG", "ADD_TO_SHORT"]:
            # When adding to position, use smaller size (e.g., 50% of new position)
            add_to_position_pct = self.config.get('add_to_position_pct', 0.5)
            risk_per_trade_pct = risk_per_trade_pct * add_to_position_pct
            # Find existing position to reference
            existing_pos = next(
                (p for p in current_positions 
                 if p.get('action') == action and p.get('status') == 'active'),
                None
            )
            if existing_pos:
                reasoning += f" | Adding to existing {action} position (ID: {existing_pos.get('position_id', 'unknown')})"
        elif position_action in ["CLOSE_LONG", "CLOSE_SHORT"]:
            # When closing, use quantity from existing position
            existing_pos = next(
                (p for p in current_positions 
                 if ((action == "SELL" and p.get('action') == 'BUY') or 
                     (action == "BUY" and p.get('action') == 'SELL')) and 
                    p.get('status') == 'active'),
                None
            )
            if existing_pos:
                quantity = existing_pos.get('quantity', 1)
                entry_price = existing_pos.get('entry_price', current_price)
                # Use existing position's stop/target or update based on current market
                stop_loss = existing_pos.get('stop_loss', stop_loss)
                take_profit = existing_pos.get('take_profit', take_profit)
                risk_amount = abs(entry_price - stop_loss) * quantity
                reasoning += f" | Closing {action} position (ID: {existing_pos.get('position_id', 'unknown')})"
                return TradingDecision(
                    action=action,
                    confidence=confidence,
                    reasoning=reasoning,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    quantity=quantity,
                    risk_amount=risk_amount,
                    agent_signals=all_signals,
                    timestamp=datetime.now(),
                    position_action=position_action
                )

        risk_amount = account_size * (risk_per_trade_pct / 100)
        stop_distance = abs(entry_price - stop_loss)

        if stop_distance > 0:
            position_value = risk_amount / (stop_distance / entry_price)
            max_position_value = account_size * (self.config.get('position_size_pct', 5.0) / 100)
            position_value = min(position_value, max_position_value)
            quantity = max(1, int(position_value / entry_price))
        else:
            quantity = 1
            risk_amount = abs(entry_price * 0.02)  # Default 2% risk

        # Add position action to reasoning
        if position_action != "OPEN_NEW":
            reasoning += f" | Action: {position_action}"

        return TradingDecision(
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            quantity=quantity,
            risk_amount=risk_amount,
            agent_signals=all_signals,
            timestamp=datetime.now(),
            position_action=position_action
        )

    def get_cycle_stats(self) -> Dict[str, Any]:
        """Get statistics about completed cycles."""
        return {
            'total_cycles': self.cycle_count,
            'last_cycle_time': self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            'symbol': self.symbol,
            'active_agents': list(self.agents.keys()),
            'config': self.config
        }

    def update_config(self, new_config: Dict[str, Any]):
        """Update orchestrator configuration."""
        self.config.update(new_config)

        # Reinitialize agents if config changed
        if 'agents' in new_config:
            self.agents = self._initialize_agents()

        logger.info(f"Orchestrator configuration updated: {list(new_config.keys())}")

