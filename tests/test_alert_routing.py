"""
Test suite for alert routing system
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from monitoring.alert_router import (
    AlertRouter, MongoDBBackend, SlackBackend, EmailBackend,
    initialize_alert_router, get_alert_router, send_alert
)


class TestMongoDBBackend:
    """Test MongoDB alert backend"""
    
    def test_send_alert_success(self):
        # Mock MongoDB database
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.alerts = mock_collection
        
        backend = MongoDBBackend(mock_db)
        
        alert = {
            'type': 'test_alert',
            'message': 'Test message',
            'severity': 'info',
            'details': {'key': 'value'}
        }
        
        result = backend.send_alert(alert)
        
        assert result is True
        assert mock_collection.insert_one.called
        call_args = mock_collection.insert_one.call_args[0][0]
        assert call_args['type'] == 'test_alert'
        assert call_args['message'] == 'Test message'
        assert call_args['severity'] == 'info'
        assert 'timestamp' in call_args
        assert call_args['status'] == 'active'
    
    def test_send_alert_failure(self):
        mock_db = Mock()
        mock_collection = Mock()
        mock_collection.insert_one.side_effect = Exception("DB error")
        mock_db.alerts = mock_collection
        
        backend = MongoDBBackend(mock_db)
        alert = {'type': 'test', 'message': 'test'}
        
        result = backend.send_alert(alert)
        
        assert result is False


class TestSlackBackend:
    """Test Slack alert backend"""
    
    def test_backend_disabled_without_webhook(self):
        backend = SlackBackend(webhook_url=None)
        assert backend.enabled is False
        
        result = backend.send_alert({'type': 'test', 'message': 'test'})
        assert result is False
    
    @patch('requests.post')
    def test_send_alert_success(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        backend = SlackBackend(webhook_url='https://hooks.slack.com/test')
        
        alert = {
            'type': 'test_alert',
            'message': 'Test message',
            'severity': 'warning',
            'details': {'key': 'value'}
        }
        
        result = backend.send_alert(alert)
        
        assert result is True
        assert mock_post.called
        call_args = mock_post.call_args
        assert call_args[0][0] == 'https://hooks.slack.com/test'
        assert 'json' in call_args[1]
        
    @patch('requests.post')
    def test_send_alert_failure(self, mock_post):
        mock_post.side_effect = Exception("Network error")
        
        backend = SlackBackend(webhook_url='https://hooks.slack.com/test')
        alert = {'type': 'test', 'message': 'test'}
        
        result = backend.send_alert(alert)
        
        assert result is False


class TestEmailBackend:
    """Test Email alert backend"""
    
    def test_backend_disabled_without_config(self):
        backend = EmailBackend()
        assert backend.enabled is False
        
        result = backend.send_alert({'type': 'test', 'message': 'test'})
        assert result is False
    
    @patch('smtplib.SMTP')
    def test_send_alert_success(self, mock_smtp):
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        backend = EmailBackend(
            smtp_host='smtp.gmail.com',
            smtp_port=587,
            smtp_user='test@example.com',
            smtp_password='password',
            from_email='alerts@example.com',
            to_emails=['user@example.com']
        )
        
        assert backend.enabled is True
        
        alert = {
            'type': 'critical_alert',
            'message': 'Critical issue',
            'severity': 'critical',
            'details': {'error': 'Something broke'}
        }
        
        result = backend.send_alert(alert)
        
        assert result is True
        assert mock_server.starttls.called
        assert mock_server.login.called
        assert mock_server.send_message.called
    
    @patch('smtplib.SMTP')
    def test_send_alert_failure(self, mock_smtp):
        mock_smtp.side_effect = Exception("SMTP error")
        
        backend = EmailBackend(
            smtp_host='smtp.gmail.com',
            smtp_user='test@example.com',
            smtp_password='password',
            from_email='alerts@example.com',
            to_emails=['user@example.com']
        )
        
        alert = {'type': 'test', 'message': 'test'}
        result = backend.send_alert(alert)
        
        assert result is False


class TestAlertRouter:
    """Test AlertRouter orchestration"""
    
    def test_route_alert_to_multiple_backends(self):
        backend1 = Mock()
        backend1.send_alert.return_value = True
        
        backend2 = Mock()
        backend2.send_alert.return_value = True
        
        router = AlertRouter([backend1, backend2])
        
        successful = router.route_alert(
            alert_type='test_alert',
            message='Test message',
            severity='info',
            details={'key': 'value'},
            source='test_suite'
        )
        
        assert successful == 2
        assert backend1.send_alert.called
        assert backend2.send_alert.called
        
        # Check alert structure
        call_args = backend1.send_alert.call_args[0][0]
        assert call_args['type'] == 'test_alert'
        assert call_args['message'] == 'Test message'
        assert call_args['severity'] == 'info'
        assert call_args['details'] == {'key': 'value'}
        assert call_args['source'] == 'test_suite'
    
    def test_route_alert_partial_failure(self):
        backend1 = Mock()
        backend1.send_alert.return_value = True
        
        backend2 = Mock()
        backend2.send_alert.return_value = False
        
        router = AlertRouter([backend1, backend2])
        
        successful = router.route_alert('test', 'message')
        
        assert successful == 1
    
    def test_route_alert_backend_exception(self):
        backend1 = Mock()
        backend1.send_alert.side_effect = Exception("Backend error")
        backend1.__class__.__name__ = 'TestBackend'
        
        backend2 = Mock()
        backend2.send_alert.return_value = True
        
        router = AlertRouter([backend1, backend2])
        
        successful = router.route_alert('test', 'message')
        
        # Should still succeed with backend2
        assert successful == 1
    
    def test_add_backend(self):
        router = AlertRouter()
        assert len(router.backends) == 0
        
        backend = Mock()
        router.add_backend(backend)
        
        assert len(router.backends) == 1
        assert router.backends[0] == backend
    
    def test_create_from_config_mongodb_only(self):
        mock_config = Mock()
        mock_db = Mock()
        
        router = AlertRouter().create_from_config(mock_config, mock_db)
        
        # Should have MongoDB backend by default
        assert len(router.backends) >= 1
        assert isinstance(router.backends[0], MongoDBBackend)
    
    def test_create_from_config_with_slack(self):
        mock_config = Mock()
        mock_config.slack_webhook_url = 'https://hooks.slack.com/test'
        mock_db = Mock()
        
        router = AlertRouter().create_from_config(mock_config, mock_db)
        
        # Should have both MongoDB and Slack backends
        assert len(router.backends) == 2
        backend_types = [type(b).__name__ for b in router.backends]
        assert 'MongoDBBackend' in backend_types
        assert 'SlackBackend' in backend_types
    
    def test_create_from_config_with_email(self):
        mock_config = Mock()
        mock_config.smtp_host = 'smtp.gmail.com'
        mock_config.smtp_port = 587
        mock_config.smtp_user = 'test@example.com'
        mock_config.smtp_password = 'password'
        mock_config.from_email = 'alerts@example.com'
        mock_config.alert_emails = 'user1@example.com,user2@example.com'
        mock_db = Mock()
        
        router = AlertRouter().create_from_config(mock_config, mock_db)
        
        # Should have both MongoDB and Email backends
        assert len(router.backends) == 2
        backend_types = [type(b).__name__ for b in router.backends]
        assert 'MongoDBBackend' in backend_types
        assert 'EmailBackend' in backend_types


class TestGlobalRouter:
    """Test global router functions"""
    
    def test_initialize_and_get_router(self):
        mock_config = Mock()
        mock_db = Mock()
        
        router = initialize_alert_router(mock_config, mock_db)
        
        assert router is not None
        assert get_alert_router() == router
    
    def test_send_alert_with_router(self):
        mock_config = Mock()
        mock_db = Mock()
        
        router = initialize_alert_router(mock_config, mock_db)
        
        # Mock the route_alert method
        router.route_alert = Mock(return_value=1)
        
        result = send_alert(
            alert_type='test',
            message='message',
            severity='info',
            details={'key': 'value'},
            source='test'
        )
        
        assert result == 1
        assert router.route_alert.called
    
    def test_send_alert_without_router_fallback(self):
        # Reset global router
        import monitoring.alert_router as ar
        ar._alert_router = None
        
        # Should fallback to logging
        result = send_alert('test', 'message', severity='info')
        
        # Returns 0 when falling back to logging
        assert result == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
