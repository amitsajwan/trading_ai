"""Scheduled learning agent that runs weekly to analyze trades and update prompts."""

import asyncio
import logging
from datetime import datetime, time
from typing import Dict, Any
from agents.learning_agent import LearningAgent
from monitoring.alerts import AlertSystem
from config.settings import settings
from pathlib import Path

logger = logging.getLogger(__name__)


class LearningScheduler:
    """Scheduler for learning agent that runs weekly on Fridays."""
    
    def __init__(self):
        """Initialize learning scheduler."""
        self.learning_agent = LearningAgent()
        self.alert_system = AlertSystem()
        self.running = False
        self.prompts_dir = Path("config/prompts")
        
    async def start(self):
        """Start the learning scheduler."""
        if self.running:
            logger.warning("Learning scheduler already running")
            return
        
        self.running = True
        logger.info("Learning scheduler started")
        
        try:
            while self.running:
                # Check if it's Friday and 4:00 PM IST
                now = datetime.now()
                
                # Friday = 4 (0=Monday, 4=Friday)
                if now.weekday() == 4:  # Friday
                    target_time = time(16, 0)  # 4:00 PM
                    current_time = now.time()
                    
                    # Check if it's around 4 PM (within 1 hour window)
                    if target_time.hour <= current_time.hour < target_time.hour + 1:
                        # Run learning analysis
                        await self._run_learning_analysis()
                        # Wait until next week (sleep for ~7 days)
                        await asyncio.sleep(7 * 24 * 3600)  # 7 days
                    else:
                        # Wait 1 hour and check again
                        await asyncio.sleep(3600)
                else:
                    # Not Friday, wait 1 hour
                    await asyncio.sleep(3600)
                    
        except asyncio.CancelledError:
            logger.info("Learning scheduler cancelled")
        except Exception as e:
            logger.error(f"Error in learning scheduler: {e}", exc_info=True)
        finally:
            self.running = False
    
    def stop(self):
        """Stop the learning scheduler."""
        self.running = False
        logger.info("Learning scheduler stopped")
    
    async def _run_learning_analysis(self):
        """Run learning agent analysis."""
        logger.info("Running weekly learning analysis...")
        
        try:
            # Analyze trades from last 7 days
            analysis = self.learning_agent.analyze_trades(days=7)
            
            if analysis.get("error"):
                logger.error(f"Learning analysis error: {analysis['error']}")
                return
            
            trades_analyzed = analysis.get("trades_analyzed", 0)
            insights = analysis.get("insights", {})
            recommendations = analysis.get("recommendations", [])
            
            # Generate summary message
            message = (
                f"📚 Weekly Learning Analysis\n\n"
                f"Trades Analyzed: {trades_analyzed}\n"
                f"Win Rate: {insights.get('win_rate', 0):.1f}%\n"
                f"Average P&L: ₹{insights.get('average_pnl', 0):.2f}\n\n"
            )
            
            # Add agent accuracy
            agent_accuracy = insights.get("agent_accuracy", {})
            if agent_accuracy:
                message += "Agent Accuracy:\n"
                for agent, accuracy in agent_accuracy.items():
                    message += f"  - {agent}: {accuracy:.1f}%\n"
                message += "\n"
            
            # Add recommendations
            if recommendations:
                message += "Recommendations:\n"
                for rec in recommendations:
                    message += f"  - {rec}\n"
            
            # Send to Slack
            await self.alert_system.send_slack_alert(message, "INFO")
            
            # Update prompts if recommendations suggest it
            if recommendations:
                await self._update_prompts(recommendations, insights)
            
            logger.info("Weekly learning analysis completed")
            
        except Exception as e:
            logger.error(f"Error running learning analysis: {e}", exc_info=True)
            await self.alert_system.send_slack_alert(
                f"Error in learning analysis: {str(e)}",
                "ERROR"
            )
    
    async def _update_prompts(self, recommendations: list, insights: Dict[str, Any]):
        """Update prompts based on recommendations."""
        logger.info("Updating prompts based on recommendations...")
        
        # This is a simplified version - in production, use LLM to generate improved prompts
        # For now, we'll just log the recommendations
        
        agent_accuracy = insights.get("agent_accuracy", {})
        
        # Find agents with low accuracy
        low_accuracy_agents = [
            agent for agent, accuracy in agent_accuracy.items()
            if accuracy < 40
        ]
        
        if low_accuracy_agents:
            logger.warning(f"Agents with low accuracy: {low_accuracy_agents}")
            # In production, generate improved prompts using LLM
            # For now, just log
            
        # Store recommendations in a file for manual review
        recommendations_file = self.prompts_dir / "recommendations.txt"
        with open(recommendations_file, "w") as f:
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write("Recommendations:\n")
            for rec in recommendations:
                f.write(f"- {rec}\n")
            f.write("\nAgent Accuracy:\n")
            for agent, accuracy in agent_accuracy.items():
                f.write(f"- {agent}: {accuracy:.1f}%\n")
        
        logger.info(f"Recommendations saved to {recommendations_file}")

