"""Alerting system for notifications."""

import logging
import httpx
from typing import Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger(__name__)


class AlertSystem:
    """Alert system for Slack/Email notifications."""
    
    def __init__(self):
        """Initialize alert system."""
        self.slack_webhook_url = settings.slack_webhook_url
        self.email_alerts = settings.email_alerts
        self.enabled = settings.enable_alerts
    
    async def send_slack_alert(self, message: str, level: str = "INFO") -> bool:
        """Send alert to Slack."""
        if not self.enabled or not self.slack_webhook_url:
            return False
        
        try:
            emoji = {
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "❌",
                "CRITICAL": "🚨"
            }.get(level, "ℹ️")
            
            payload = {
                "text": f"{emoji} {level}: {message}"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.slack_webhook_url,
                    json=payload,
                    timeout=5.0
                )
                response.raise_for_status()
            
            logger.info(f"Slack alert sent: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")
            return False
    
    def send_email_alert(self, subject: str, message: str) -> bool:
        """Send email alert (placeholder - implement with SMTP)."""
        if not self.enabled or not self.email_alerts:
            return False
        
        # TODO: Implement email sending via SMTP
        logger.info(f"Email alert (not implemented): {subject} - {message}")
        return False
    
    async def alert_circuit_breaker(self, checks: Dict[str, bool]) -> None:
        """Alert when circuit breaker is triggered."""
        triggered_checks = [name for name, triggered in checks.items() if triggered]
        message = f"Circuit breaker triggered! Checks: {', '.join(triggered_checks)}"
        await self.send_slack_alert(message, "CRITICAL")
    
    async def alert_trade_executed(self, trade_details: Dict[str, Any]) -> None:
        """Alert when a trade is executed."""
        message = (
            f"Trade executed: {trade_details.get('signal')} "
            f"{trade_details.get('quantity')} @ {trade_details.get('entry_price')}"
        )
        await self.send_slack_alert(message, "INFO")
    
    async def alert_daily_summary(self, summary: Dict[str, Any]) -> None:
        """Send daily trading summary."""
        message = (
            f"Daily Summary:\n"
            f"P&L: {summary.get('pnl', 0):.2f}\n"
            f"Trades: {summary.get('trades_count', 0)}\n"
            f"Win Rate: {summary.get('win_rate', 0):.1f}%"
        )
        await self.send_slack_alert(message, "INFO")

