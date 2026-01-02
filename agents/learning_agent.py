"""Learning Agent for post-trade analysis and prompt refinement."""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from agents.base_agent import BaseAgent
from agents.state import AgentState
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings

logger = logging.getLogger(__name__)


class LearningAgent(BaseAgent):
    """Learning agent for post-trade analysis and strategy improvement."""
    
    def __init__(self):
        """Initialize learning agent."""
        super().__init__("learning", self._get_default_prompt())
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.trades_collection = get_collection(self.db, "trades_executed")
        self.agent_decisions_collection = get_collection(self.db, "agent_decisions")
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        return """You are the Learning Agent for a {instrument_name} trading system.
Your role: Analyze completed trades, identify patterns, and suggest improvements to agent prompts."""
    
    def analyze_trades(self, days: int = 7) -> Dict[str, Any]:
        """Analyze trades from the last N days."""
        logger.info(f"Analyzing trades from last {days} days...")
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get closed trades
            trades = list(self.trades_collection.find({
                "exit_timestamp": {"$gte": cutoff_date.isoformat()},
                "status": "CLOSED"
            }))
            
            if not trades:
                logger.warning("No closed trades found for analysis")
                return {"trades_analyzed": 0}
            
            # Analyze each trade
            analysis_results = []
            for trade in trades:
                analysis = self._analyze_single_trade(trade)
                analysis_results.append(analysis)
            
            # Aggregate insights
            insights = self._aggregate_insights(analysis_results)
            
            return {
                "trades_analyzed": len(trades),
                "insights": insights,
                "recommendations": self._generate_recommendations(insights)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trades: {e}")
            return {"error": str(e)}
    
    def _analyze_single_trade(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single trade."""
        agent_decisions = trade.get("agent_decisions", {})
        pnl = trade.get("pnl", 0)
        pnl_percent = trade.get("pnl_percent", 0)
        
        # Determine if trade was successful
        was_profitable = pnl > 0
        
        # Identify which agent's input was most critical
        # This is a simplified version - in production, use more sophisticated analysis
        most_critical_agent = "portfolio_manager"  # Default
        
        # Check technical analysis accuracy
        technical = agent_decisions.get("technical", {})
        if technical.get("trend_direction") == "UP" and was_profitable:
            most_critical_agent = "technical"
        elif technical.get("trend_direction") == "DOWN" and not was_profitable:
            most_critical_agent = "technical"
        
        return {
            "trade_id": trade.get("trade_id"),
            "was_profitable": was_profitable,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "most_critical_agent": most_critical_agent,
            "signal": trade.get("signal")
        }
    
    def _aggregate_insights(self, analysis_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate insights from multiple trade analyses."""
        total_trades = len(analysis_results)
        profitable_trades = sum(1 for a in analysis_results if a["was_profitable"])
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Agent performance
        agent_performance = {}
        for result in analysis_results:
            agent = result["most_critical_agent"]
            if agent not in agent_performance:
                agent_performance[agent] = {"correct": 0, "total": 0}
            agent_performance[agent]["total"] += 1
            if result["was_profitable"]:
                agent_performance[agent]["correct"] += 1
        
        # Calculate accuracy for each agent
        agent_accuracy = {
            agent: (perf["correct"] / perf["total"] * 100) if perf["total"] > 0 else 0
            for agent, perf in agent_performance.items()
        }
        
        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "agent_accuracy": agent_accuracy,
            "average_pnl": sum(a["pnl"] for a in analysis_results) / total_trades if total_trades > 0 else 0
        }
    
    def _generate_recommendations(self, insights: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on insights."""
        recommendations = []
        
        win_rate = insights.get("win_rate", 0)
        if win_rate < 50:
            recommendations.append("Win rate is below 50%. Consider tightening entry criteria.")
        
        agent_accuracy = insights.get("agent_accuracy", {})
        worst_agent = min(agent_accuracy.items(), key=lambda x: x[1]) if agent_accuracy else None
        if worst_agent and worst_agent[1] < 40:
            recommendations.append(f"{worst_agent[0]} agent accuracy is low ({worst_agent[1]:.1f}%). Review its prompts.")
        
        return recommendations
    
    def process(self, state: AgentState) -> AgentState:
        """Process learning analysis (typically called post-market)."""
        logger.info("Processing learning analysis...")
        
        # Analyze recent trades
        analysis = self.analyze_trades(days=7)
        
        output = {
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }
        
        explanation = f"Learning analysis: {analysis.get('trades_analyzed', 0)} trades analyzed, "
        explanation += f"win_rate={analysis.get('insights', {}).get('win_rate', 0):.1f}%"
        
        self.update_state(state, output, explanation)
        
        return state

