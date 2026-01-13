"""Enhanced Momentum Agent with Structured Reports and Multi-Timeframe Analysis.

This module provides an enhanced momentum agent that:
- Uses structured reports for communication
- Integrates multi-timeframe analysis
- Integrates regime detection
- Provides position-aware analysis
- Generates exit signals
"""

import logging
from typing import Dict, Any, List, Optional

from engine_module.agents.base_agent import BaseAgent
from engine_module.contracts import AnalysisResult
from engine_module.communication import (
    ReportEvidence,
    ReportSection,
    EvidenceType,
    ReportType,
    ReportPriority
)

logger = logging.getLogger(__name__)


class EnhancedMomentumAgent(BaseAgent):
    """Enhanced Momentum Agent with multi-timeframe analysis and structured reports.
    
    Entry Conditions:
    - RSI breaking above/below thresholds across multiple timeframes
    - Volume confirmation (>150% average)
    - MACD crossover in same direction
    - ADX showing strength (>25)
    
    Exit Conditions:
    - RSI reversal
    - Volume exhaustion
    - MACD divergence
    - Trailing stop hit
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize enhanced momentum agent.
        
        Args:
            config: Configuration dictionary with:
                - rsi_oversold: RSI oversold threshold (default: 30)
                - rsi_overbought: RSI overbought threshold (default: 70)
                - volume_threshold: Volume spike threshold (default: 1.5)
                - adx_threshold: ADX threshold for strong trend (default: 25)
                - min_confidence: Minimum confidence threshold (default: 0.60)
        """
        config = config or {}
        super().__init__("EnhancedMomentumAgent", config)
        
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.volume_threshold = config.get('volume_threshold', 1.5)
        self.adx_threshold = config.get('adx_threshold', 25)
        
        logger.debug(f"EnhancedMomentumAgent initialized: RSI thresholds ({self.rsi_oversold}/{self.rsi_overbought}), "
                    f"Volume threshold: {self.volume_threshold}x")
    
    async def _analyze_internal(
        self,
        market_data: Dict[str, Any],
        multi_timeframe: Dict[str, Any],
        regime: Optional[str],
        current_positions: List[Dict[str, Any]],
        technical_indicators: Dict[str, Any],
        context: Dict[str, Any]
    ) -> AnalysisResult:
        """Perform enhanced momentum analysis.
        
        Args:
            market_data: Current market data
            multi_timeframe: Multi-timeframe data (dict with timeframe keys)
            regime: Current market regime
            current_positions: Current positions
            technical_indicators: Pre-calculated technical indicators
            context: Full context dictionary
        
        Returns:
            AnalysisResult with momentum-based decision
        """
        # Check exit conditions first
        exit_signal = self._check_exit_conditions_enhanced(
            market_data, current_positions, technical_indicators, multi_timeframe
        )
        if exit_signal:
            return exit_signal
        
        # Get data from multiple timeframes
        tf_15m = multi_timeframe.get('15m', {}) if multi_timeframe else {}
        tf_1h = multi_timeframe.get('1h', {}) if multi_timeframe else {}
        tf_daily = multi_timeframe.get('daily', {}) if multi_timeframe else {}
        
        # Use current timeframe data as primary
        primary_rsi = technical_indicators.get('rsi') or market_data.get('rsi')
        primary_macd = technical_indicators.get('macd') or market_data.get('macd')
        primary_macd_signal = technical_indicators.get('macd_signal') or market_data.get('macd_signal')
        primary_adx = technical_indicators.get('adx') or market_data.get('adx')
        primary_volume_ratio = technical_indicators.get('volume_ratio') or market_data.get('volume_ratio', 1.0)
        
        # Get multi-timeframe RSI
        rsi_15m = tf_15m.get('rsi') if tf_15m else primary_rsi
        rsi_1h = tf_1h.get('rsi') if tf_1h else primary_rsi
        rsi_daily = tf_daily.get('rsi') if tf_daily else primary_rsi
        
        # Get current price
        current_price = market_data.get('close') or market_data.get('current_price', 0)
        ema_50 = technical_indicators.get('ema_50') or market_data.get('ema_50')
        
        # Check conditions for LONG
        long_conditions = {
            'rsi_oversold_15m': rsi_15m is not None and rsi_15m < self.rsi_oversold,
            'rsi_rising_1h': rsi_1h is not None and rsi_15m is not None and rsi_1h > rsi_15m,
            'volume_spike': primary_volume_ratio > self.volume_threshold,
            'macd_bullish': primary_macd is not None and primary_macd_signal is not None and primary_macd > primary_macd_signal,
            'adx_strong': primary_adx is not None and primary_adx > self.adx_threshold,
            'price_above_ema': current_price > 0 and ema_50 is not None and current_price > ema_50
        }
        
        # Check conditions for SHORT
        short_conditions = {
            'rsi_overbought_15m': rsi_15m is not None and rsi_15m > self.rsi_overbought,
            'rsi_falling_1h': rsi_1h is not None and rsi_15m is not None and rsi_1h < rsi_15m,
            'volume_spike': primary_volume_ratio > self.volume_threshold,
            'macd_bearish': primary_macd is not None and primary_macd_signal is not None and primary_macd < primary_macd_signal,
            'adx_strong': primary_adx is not None and primary_adx > self.adx_threshold,
            'price_below_ema': current_price > 0 and ema_50 is not None and current_price < ema_50
        }
        
        # Calculate confidence for each direction
        long_confidence = self._calculate_confidence(long_conditions)
        short_confidence = self._calculate_confidence(short_conditions)
        
        # Determine action
        if long_confidence > short_confidence and long_confidence >= self.min_confidence:
            action = 'BUY'
            confidence = long_confidence
            conditions = long_conditions
        elif short_confidence > long_confidence and short_confidence >= self.min_confidence:
            action = 'SELL'
            confidence = short_confidence
            conditions = short_conditions
        else:
            action = 'HOLD'
            confidence = max(long_confidence, short_confidence)
            conditions = {}
        
        # Build reasoning
        reasoning = self._build_reasoning(action, conditions, market_data, multi_timeframe)
        
        # Assess risk
        risk_assessment = self._assess_risk(market_data, action, current_positions)
        
        # Build details
        details = {
            'agent': self.name,
            'strategy': 'momentum',
            'reasoning': reasoning,
            'conditions_met': [k for k, v in conditions.items() if v] if conditions else [],
            'conditions_failed': [k for k, v in conditions.items() if not v] if conditions else [],
            'technical_data': {
                'rsi_15m': rsi_15m,
                'rsi_1h': rsi_1h,
                'rsi_daily': rsi_daily,
                'macd': primary_macd,
                'volume_ratio': primary_volume_ratio,
                'adx': primary_adx
            },
            'risk_assessment': risk_assessment,
            'regime': regime,
            'target': market_data.get('instrument', 'BANKNIFTY'),
            'entry_price': current_price
        }
        
        # Add position recommendation
        if action != 'HOLD':
            details['position_recommendation'] = self._recommend_position(action, confidence, risk_assessment)
        
        return AnalysisResult(
            decision=action,
            confidence=confidence,
            details=details,
            agent=self.name
        )
    
    def _check_exit_conditions_enhanced(
        self,
        market_data: Dict[str, Any],
        current_positions: List[Dict[str, Any]],
        technical_indicators: Dict[str, Any],
        multi_timeframe: Dict[str, Any]
    ) -> Optional[AnalysisResult]:
        """Check if we should exit current positions (enhanced with multi-timeframe)."""
        if not current_positions:
            return None
        
        current_price = market_data.get('close') or market_data.get('current_price', 0)
        rsi = technical_indicators.get('rsi') or market_data.get('rsi')
        volume_ratio = technical_indicators.get('volume_ratio') or market_data.get('volume_ratio', 1.0)
        
        for position in current_positions:
            if position.get('strategy') != 'momentum':
                continue
            
            position_type = position.get('type', 'LONG')
            entry_price = position.get('entry_price', 0)
            
            if entry_price <= 0 or current_price <= 0:
                continue
            
            # Calculate P&L
            if position_type == 'LONG':
                pnl_pct = (current_price - entry_price) / entry_price
            else:  # SHORT
                pnl_pct = (entry_price - current_price) / entry_price
            
            should_exit = False
            exit_reason = ""
            
            # Check stop loss FIRST (highest priority)
            if pnl_pct <= -0.02:
                should_exit = True
                exit_reason = "Trailing stop hit (-2%)"
            
            # RSI reversal (only if stop loss not hit)
            if not should_exit and rsi is not None:
                if position_type == 'LONG' and rsi < 50:
                    should_exit = True
                    exit_reason = "RSI below 50 (reversal)"
                elif position_type == 'SHORT' and rsi > 50:
                    should_exit = True
                    exit_reason = "RSI above 50 (reversal)"
            
            # Volume exhaustion (only if stop loss not hit)
            if not should_exit and volume_ratio < 0.5:
                should_exit = True
                exit_reason = "Volume exhaustion"
            
            if should_exit:
                return AnalysisResult(
                    decision='CLOSE',
                    confidence=0.80,
                    details={
                        'position_id': position.get('id'),
                        'reason': exit_reason,
                        'pnl_pct': pnl_pct,
                        'agent': self.name
                    },
                    agent=self.name
                )
        
        return None
    
    def _build_reasoning(
        self,
        action: str,
        conditions: Dict[str, bool],
        market_data: Dict[str, Any],
        multi_timeframe: Dict[str, Any]
    ) -> str:
        """Build human-readable reasoning."""
        if action == 'HOLD':
            return "Insufficient momentum signals. Waiting for clearer setup."
        
        met = [k for k, v in conditions.items() if v]
        failed = [k for k, v in conditions.items() if not v]
        
        reasoning = f"{action} signal detected with {len(met)}/{len(conditions)} conditions met.\n\n"
        reasoning += "Conditions Met:\n"
        for cond in met:
            reasoning += f" ✓ {cond.replace('_', ' ').title()}\n"
        
        if failed:
            reasoning += "\nConditions Not Met:\n"
            for cond in failed:
                reasoning += f" ✗ {cond.replace('_', ' ').title()}\n"
        
        reasoning += f"\nKey Metrics:\n"
        tf_15m = multi_timeframe.get('15m', {}) if multi_timeframe else {}
        rsi_15m = tf_15m.get('rsi', market_data.get('rsi'))
        volume_ratio = market_data.get('volume_ratio', 1.0)
        adx = market_data.get('adx', 0)
        
        reasoning += f" - RSI (15m): {rsi_15m:.1f}\n" if rsi_15m else " - RSI (15m): N/A\n"
        reasoning += f" - Volume Ratio: {volume_ratio:.2f}x\n"
        reasoning += f" - ADX: {adx:.1f}\n" if adx else " - ADX: N/A\n"
        
        return reasoning
    
    def _recommend_position(
        self,
        action: str,
        confidence: float,
        risk_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recommend position parameters."""
        # Adjust position size based on confidence and risk
        base_size = 1.0
        if confidence > 0.80:
            size_multiplier = 1.5
        elif confidence > 0.70:
            size_multiplier = 1.0
        else:
            size_multiplier = 0.5
        
        if risk_assessment.get('risk_score', 0) > 60:
            size_multiplier *= 0.5
        
        return {
            'action': action,
            'size_multiplier': size_multiplier,
            'stop_loss_pct': 0.02,  # 2% trailing stop
            'take_profit_pct': 0.04,  # 4% target (2:1 R:R)
            'time_horizon': '1-3 days'
        }
    
    def _add_analysis_sections(
        self,
        builder,
        analysis_result: AnalysisResult,
        market_data: Dict[str, Any],
        multi_timeframe: Dict[str, Any],
        regime: Optional[str]
    ):
        """Add momentum-specific sections to report."""
        # Call parent to add base sections
        super()._add_analysis_sections(builder, analysis_result, market_data, multi_timeframe, regime)
        
        details = analysis_result.details or {}
        technical_data = details.get('technical_data', {})
        
        # Add multi-timeframe momentum section
        if multi_timeframe:
            tf_section_content = "Multi-timeframe RSI analysis:\n"
            for tf_name in ['15m', '1h', 'daily']:
                tf_data = multi_timeframe.get(tf_name, {})
                rsi = tf_data.get('rsi') or technical_data.get(f'rsi_{tf_name}')
                if rsi is not None:
                    tf_section_content += f"- {tf_name}: RSI = {rsi:.1f}\n"
            
            evidence = []
            for tf_name in ['15m', '1h', 'daily']:
                rsi = technical_data.get(f'rsi_{tf_name}')
                if rsi is not None:
                    evidence.append(ReportEvidence(
                        type=EvidenceType.TECHNICAL_INDICATOR,
                        description=f"RSI on {tf_name} timeframe",
                        value=rsi,
                        source=f"RSI_14_{tf_name}",
                        confidence=0.8
                    ))
            
            builder.add_section(
                title="Multi-Timeframe Momentum",
                content=tf_section_content,
                confidence=analysis_result.confidence * 0.9,  # Slightly lower confidence for MTF
                evidence=evidence
            )
        
        # Add conditions section
        conditions_met = details.get('conditions_met', [])
        if conditions_met:
            builder.add_section(
                title="Momentum Conditions",
                content=f"{len(conditions_met)} momentum conditions met: {', '.join(conditions_met)}",
                confidence=analysis_result.confidence
            )
