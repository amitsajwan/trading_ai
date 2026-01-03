"""Review Agent - Analyzes trade outcomes and updates strategy."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from agents.base_agent import BaseAgent
from agents.state import AgentState
from config.settings import settings

logger = logging.getLogger(__name__)


class ReviewAgent(BaseAgent):
    """Review agent that analyzes trade outcomes and learns from them."""
    
    def __init__(self):
        """Initialize review agent."""
        super().__init__("review", self._get_default_prompt())
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        instrument_name = settings.instrument_name
        return f"""You are the Review Agent for a {instrument_name} trading system.
Your role: Analyze completed trades and strategy performance to identify what worked and what didn't.
Learn from outcomes and provide insights to improve future strategies."""
    
    def process(
        self,
        state: AgentState,
        recent_trades: Optional[List[Dict[str, Any]]] = None,
        previous_strategy: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Review trades and strategy performance."""
        logger.info("Processing review and learning...")
        
        try:
            # Gather context
            recent_trades = recent_trades or []
            previous_strategy = previous_strategy or {}
            
            # Analyze trades
            trade_analysis = self._analyze_trades(recent_trades)
            
            # Analyze strategy performance
            strategy_analysis = self._analyze_strategy_performance(
                previous_strategy,
                trade_analysis
            )
            
            # Generate learnings
            learnings = self._generate_learnings(
                trade_analysis,
                strategy_analysis,
                state
            )
            
            # Create review output
            review_output = {
                "trade_analysis": trade_analysis,
                "strategy_analysis": strategy_analysis,
                "learnings": learnings,
                "recommendations": self._generate_recommendations(learnings),
                "agent_performance": self._assess_agent_performance(state, trade_analysis),
                "confidence_score": self._calculate_review_confidence(trade_analysis, strategy_analysis)
            }
            
            logger.info(f"Review completed: {len(recent_trades)} trades analyzed")
            return review_output
            
        except Exception as e:
            logger.error(f"Error in review agent: {e}", exc_info=True)
            return {
                "error": str(e),
                "trade_analysis": {},
                "strategy_analysis": {},
                "learnings": [],
                "confidence_score": 0.0
            }
    
    def _analyze_trades(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze recent trades."""
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0
            }
        
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) <= 0]
        
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        avg_profit = sum(t.get("pnl", 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = abs(sum(t.get("pnl", 0) for t in losing_trades) / len(losing_trades)) if losing_trades else 0
        
        profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0
        
        return {
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": len(winning_trades) / len(trades) if trades else 0,
            "total_pnl": total_pnl,
            "avg_profit": avg_profit,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "trades": trades
        }
    
    def _analyze_strategy_performance(
        self,
        strategy: Dict[str, Any],
        trade_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze how well the strategy performed."""
        if not strategy:
            return {
                "strategy_effectiveness": 0.0,
                "entry_quality": 0.0,
                "exit_quality": 0.0,
                "risk_management": 0.0
            }
        
        # Calculate strategy effectiveness
        win_rate = trade_analysis.get("win_rate", 0)
        profit_factor = trade_analysis.get("profit_factor", 0)
        strategy_effectiveness = (win_rate * 0.5) + (min(profit_factor, 2.0) / 2.0 * 0.5)
        
        # Analyze entry/exit quality from trades
        trades = trade_analysis.get("trades", [])
        entry_quality = self._assess_entry_quality(trades)
        exit_quality = self._assess_exit_quality(trades)
        risk_management = self._assess_risk_management(trades, strategy)
        
        return {
            "strategy_effectiveness": strategy_effectiveness,
            "entry_quality": entry_quality,
            "exit_quality": exit_quality,
            "risk_management": risk_management,
            "strategy_id": strategy.get("strategy_id"),
            "expected_vs_actual": self._compare_expected_vs_actual(strategy, trade_analysis)
        }
    
    def _assess_entry_quality(self, trades: List[Dict[str, Any]]) -> float:
        """Assess quality of trade entries."""
        if not trades:
            return 0.5  # Neutral
        
        # Check slippage, timing, etc.
        entry_scores = []
        for trade in trades:
            entry_price = trade.get("entry_price", 0)
            intended_entry = trade.get("intended_entry_price", entry_price)
            
            if intended_entry > 0:
                slippage_pct = abs(entry_price - intended_entry) / intended_entry
                # Lower slippage = better (score 1.0 - slippage_pct * 10)
                score = max(0, 1.0 - (slippage_pct * 10))
                entry_scores.append(score)
        
        return sum(entry_scores) / len(entry_scores) if entry_scores else 0.5
    
    def _assess_exit_quality(self, trades: List[Dict[str, Any]]) -> float:
        """Assess quality of trade exits."""
        if not trades:
            return 0.5
        
        exit_scores = []
        for trade in trades:
            exit_type = trade.get("exit_type", "UNKNOWN")
            pnl = trade.get("pnl", 0)
            
            # Reward take-profit hits, penalize stop-loss hits
            if exit_type == "TAKE_PROFIT":
                exit_scores.append(1.0)
            elif exit_type == "STOP_LOSS":
                exit_scores.append(0.3)
            elif pnl > 0:
                exit_scores.append(0.7)  # Manual exit with profit
            else:
                exit_scores.append(0.4)  # Manual exit with loss
        
        return sum(exit_scores) / len(exit_scores) if exit_scores else 0.5
    
    def _assess_risk_management(
        self,
        trades: List[Dict[str, Any]],
        strategy: Dict[str, Any]
    ) -> float:
        """Assess risk management effectiveness."""
        if not trades:
            return 0.5
        
        # Check if stop-losses were hit appropriately
        # Check if position sizing was appropriate
        # Check if risk limits were respected
        
        risk_scores = []
        for trade in trades:
            risk_pct = trade.get("risk_pct", 0)
            max_risk = strategy.get("position_sizing", {}).get("risk_pct", 2.0)
            
            # Reward trades within risk limits
            if risk_pct <= max_risk:
                risk_scores.append(1.0)
            else:
                risk_scores.append(0.5)
        
        return sum(risk_scores) / len(risk_scores) if risk_scores else 0.5
    
    def _compare_expected_vs_actual(
        self,
        strategy: Dict[str, Any],
        trade_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare expected strategy performance vs actual."""
        expected_win_rate = strategy.get("agent_reasoning", {}).get("expected_win_rate", 0.5)
        actual_win_rate = trade_analysis.get("win_rate", 0)
        
        expected_pnl = strategy.get("agent_reasoning", {}).get("expected_pnl", 0)
        actual_pnl = trade_analysis.get("total_pnl", 0)
        
        return {
            "win_rate_diff": actual_win_rate - expected_win_rate,
            "pnl_diff": actual_pnl - expected_pnl,
            "prediction_accuracy": 1.0 - abs(actual_win_rate - expected_win_rate)
        }
    
    def _generate_learnings(
        self,
        trade_analysis: Dict[str, Any],
        strategy_analysis: Dict[str, Any],
        state: AgentState
    ) -> List[str]:
        """Generate learnings from analysis."""
        learnings = []
        
        # Trade-level learnings
        win_rate = trade_analysis.get("win_rate", 0)
        if win_rate > 0.6:
            learnings.append("High win rate achieved - entry conditions were effective")
        elif win_rate < 0.4:
            learnings.append("Low win rate - entry conditions need refinement")
        
        profit_factor = trade_analysis.get("profit_factor", 0)
        if profit_factor > 1.5:
            learnings.append("Strong profit factor - risk/reward was favorable")
        elif profit_factor < 1.0:
            learnings.append("Profit factor below 1.0 - need better risk/reward ratios")
        
        # Strategy-level learnings
        entry_quality = strategy_analysis.get("entry_quality", 0.5)
        if entry_quality > 0.7:
            learnings.append("Good entry quality - timing and conditions were appropriate")
        elif entry_quality < 0.5:
            learnings.append("Poor entry quality - need to improve entry conditions")
        
        exit_quality = strategy_analysis.get("exit_quality", 0.5)
        if exit_quality > 0.7:
            learnings.append("Good exit quality - stop-loss and take-profit worked well")
        elif exit_quality < 0.5:
            learnings.append("Poor exit quality - need to refine exit rules")
        
        return learnings
    
    def _generate_recommendations(self, learnings: List[str]) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        for learning in learnings:
            if "entry conditions" in learning.lower():
                recommendations.append("Review and refine entry conditions in next strategy")
            elif "exit" in learning.lower():
                recommendations.append("Adjust stop-loss and take-profit levels")
            elif "risk/reward" in learning.lower():
                recommendations.append("Improve risk/reward ratios in position sizing")
            elif "win rate" in learning.lower():
                recommendations.append("Update agent weights based on performance")
        
        return recommendations
    
    def _assess_agent_performance(
        self,
        state: AgentState,
        trade_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """Assess which agents performed best."""
        # This would compare agent predictions vs actual outcomes
        # For now, return placeholder
        return {
            "technical": 0.7,
            "fundamental": 0.65,
            "sentiment": 0.6,
            "macro": 0.68
        }
    
    def _calculate_review_confidence(
        self,
        trade_analysis: Dict[str, Any],
        strategy_analysis: Dict[str, Any]
    ) -> float:
        """Calculate confidence in review analysis."""
        num_trades = trade_analysis.get("total_trades", 0)
        
        if num_trades == 0:
            return 0.0
        
        # More trades = higher confidence
        trade_confidence = min(1.0, num_trades / 10.0)
        
        # Strategy effectiveness = confidence in strategy analysis
        strategy_confidence = strategy_analysis.get("strategy_effectiveness", 0.5)
        
        return (trade_confidence * 0.5) + (strategy_confidence * 0.5)

