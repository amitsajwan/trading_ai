"""
Alert routing system with multiple backends (MongoDB, Slack, Email)
Allows flexible alert delivery with pluggable backends
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


class AlertBackend(ABC):
    """Base class for alert delivery backends"""
    
    @abstractmethod
    def send_alert(self, alert: Dict[str, Any]) -> bool:
        """Send alert through this backend. Returns True if successful."""
        pass


class MongoDBBackend(AlertBackend):
    """Store alerts in MongoDB alerts collection"""
    
    def __init__(self, db):
        self.db = db
        
    def send_alert(self, alert: Dict[str, Any]) -> bool:
        try:
            alert_doc = {
                **alert,
                'timestamp': datetime.utcnow(),
                'status': 'active'
            }
            self.db.alerts.insert_one(alert_doc)
            logger.info(f"Stored alert in MongoDB: {alert.get('type', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to store alert in MongoDB: {e}")
            return False


class SlackBackend(AlertBackend):
    """Send alerts to Slack webhook (optional, requires slack_webhook_url)"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self.enabled = webhook_url is not None
        
    def send_alert(self, alert: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
            
        try:
            import requests
            
            severity = alert.get('severity', 'info')
            emoji = {
                'critical': ':rotating_light:',
                'warning': ':warning:',
                'info': ':information_source:'
            }.get(severity, ':bell:')
            
            message = {
                'text': f"{emoji} *{alert.get('type', 'Alert')}*",
                'blocks': [
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': f"{emoji} *{alert.get('type', 'Alert')}*\n{alert.get('message', 'No message')}"
                        }
                    }
                ]
            }
            
            # Add details if available
            if alert.get('details'):
                message['blocks'].append({
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f"```{json.dumps(alert['details'], indent=2)}```"
                    }
                })
            
            response = requests.post(self.webhook_url, json=message, timeout=5)
            response.raise_for_status()
            logger.info(f"Sent alert to Slack: {alert.get('type', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert to Slack: {e}")
            return False


class EmailBackend(AlertBackend):
    """Send alerts via email (optional, requires SMTP configuration)"""
    
    def __init__(self, smtp_host: Optional[str] = None, smtp_port: int = 587,
                 smtp_user: Optional[str] = None, smtp_password: Optional[str] = None,
                 from_email: Optional[str] = None, to_emails: Optional[List[str]] = None):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_emails = to_emails or []
        self.enabled = all([smtp_host, smtp_user, smtp_password, from_email, to_emails])
        
    def send_alert(self, alert: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
            
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            severity = alert.get('severity', 'info')
            subject = f"[{severity.upper()}] {alert.get('type', 'Alert')}"
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            
            # Plain text version
            text = f"{alert.get('message', 'No message')}\n\n"
            if alert.get('details'):
                text += f"Details:\n{json.dumps(alert['details'], indent=2)}"
            
            # HTML version
            html = f"""
            <html>
              <body>
                <h2 style="color: {'red' if severity == 'critical' else 'orange' if severity == 'warning' else 'blue'}">
                  {alert.get('type', 'Alert')}
                </h2>
                <p>{alert.get('message', 'No message')}</p>
            """
            if alert.get('details'):
                html += f"<pre>{json.dumps(alert['details'], indent=2)}</pre>"
            html += "</body></html>"
            
            msg.attach(MIMEText(text, 'plain'))
            msg.attach(MIMEText(html, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Sent alert via email: {alert.get('type', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert via email: {e}")
            return False


class AlertRouter:
    """Routes alerts to multiple backends with priority-based delivery"""
    
    def __init__(self, backends: Optional[List[AlertBackend]] = None):
        self.backends = backends or []
        
    def add_backend(self, backend: AlertBackend):
        """Add a new backend to the router"""
        self.backends.append(backend)
        
    def route_alert(self, alert_type: str, message: str, 
                    severity: str = 'info', details: Optional[Dict[str, Any]] = None,
                    source: Optional[str] = None) -> int:
        """
        Route alert to all configured backends
        
        Args:
            alert_type: Type of alert (e.g., 'incomplete_json', 'provider_error')
            message: Human-readable alert message
            severity: 'critical', 'warning', or 'info'
            details: Additional context (dict)
            source: Source component (e.g., 'base_agent', 'llm_monitor')
            
        Returns:
            Number of backends that successfully delivered the alert
        """
        alert = {
            'type': alert_type,
            'message': message,
            'severity': severity,
            'details': details or {},
            'source': source or 'unknown'
        }
        
        successful = 0
        for backend in self.backends:
            try:
                if backend.send_alert(alert):
                    successful += 1
            except Exception as e:
                logger.error(f"Backend {backend.__class__.__name__} failed: {e}")
                
        if successful == 0:
            logger.warning(f"Alert not delivered by any backend: {alert_type}")
        else:
            logger.info(f"Alert delivered by {successful}/{len(self.backends)} backends")
            
        return successful
    
    def create_from_config(self, config, db):
        """
        Factory method to create AlertRouter from TradingConfig
        
        Args:
            config: TradingConfig instance
            db: MongoDB database instance
            
        Returns:
            Configured AlertRouter instance
        """
        # Always add MongoDB backend
        self.add_backend(MongoDBBackend(db))
        
        # Add Slack backend if configured (ensure it's a non-empty string)
        slack_webhook = getattr(config, 'slack_webhook_url', None)
        if isinstance(slack_webhook, str) and slack_webhook.strip():
            self.add_backend(SlackBackend(slack_webhook))
            logger.info("Slack alerts enabled")
        
        # Add Email backend if configured (validate the config values are real strings/lists)
        smtp_host = getattr(config, 'smtp_host', None)
        smtp_user = getattr(config, 'smtp_user', None)
        smtp_password = getattr(config, 'smtp_password', None)
        from_email = getattr(config, 'from_email', None)
        to_emails = getattr(config, 'alert_emails', None)
        
        if (isinstance(smtp_host, str) and smtp_host.strip() and
            isinstance(smtp_user, str) and smtp_user.strip() and
            isinstance(smtp_password, str) and smtp_password.strip() and
            isinstance(from_email, str) and from_email.strip() and
            (isinstance(to_emails, str) and to_emails.strip() or isinstance(to_emails, (list, tuple)))):
            smtp_port = getattr(config, 'smtp_port', 587)
            self.add_backend(EmailBackend(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                from_email=from_email,
                to_emails=to_emails.split(',') if isinstance(to_emails, str) else to_emails
            ))
            logger.info("Email alerts enabled")
            
        return self


# Global router instance (initialized by system)
_alert_router: Optional[AlertRouter] = None


def initialize_alert_router(config, db) -> AlertRouter:
    """Initialize global alert router from config"""
    global _alert_router
    _alert_router = AlertRouter().create_from_config(config, db)
    return _alert_router


def get_alert_router() -> Optional[AlertRouter]:
    """Get global alert router instance"""
    return _alert_router


def send_alert(alert_type: str, message: str, severity: str = 'info', 
               details: Optional[Dict[str, Any]] = None, source: Optional[str] = None) -> int:
    """
    Convenience function to send alert through global router
    Falls back to logging if router not initialized
    """
    if _alert_router:
        return _alert_router.route_alert(alert_type, message, severity, details, source)
    else:
        # Fallback to logging if router not initialized
        log_method = {
            'critical': logger.critical,
            'warning': logger.warning,
            'info': logger.info
        }.get(severity, logger.info)
        log_method(f"[{alert_type}] {message} | {details}")
        return 0
