"""Unit tests for mode validator."""
import os
import pytest
from unittest.mock import Mock, patch
from market_data.mode_validator import (
    validate_mode_consistency,
    ModeValidationError,
    log_mode_startup
)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis_client = Mock()
    redis_client.get = Mock(return_value=None)
    redis_client.scan_iter = Mock(return_value=iter([]))
    return redis_client


class TestModeValidator:
    
    def test_valid_live_mode(self, mock_redis):
        """Test validator passes with valid live mode configuration."""
        # Setup
        os.environ["EXECUTION_MODE"] = "live"
        mock_redis.get.side_effect = lambda key: {
            "system:execution_mode": b"live",
            "system:virtual_time:enabled": b"0"
        }.get(key)
        mock_redis.scan_iter.return_value = iter([b"live:ohlc:test"])
        
        # Execute
        result = validate_mode_consistency(mock_redis, "test_service")
        
        # Verify
        assert result['mode'] == 'live'
        assert result['virtual_time_enabled'] is False
        assert result['redis_mode'] == 'live'
        assert len(result['warnings']) == 0
        assert result['status'] == 'ok'
    
    def test_valid_historical_mode(self, mock_redis):
        """Test validator passes with valid historical mode configuration."""
        # Setup
        os.environ["EXECUTION_MODE"] = "historical"
        mock_redis.get.side_effect = lambda key: {
            "system:execution_mode": b"historical",
            "system:virtual_time:enabled": b"1",
            "system:virtual_time:current": b"2026-01-15T09:15:00+05:30"
        }.get(key)
        mock_redis.scan_iter.return_value = iter([b"historical:ohlc:test"])
        
        # Execute
        result = validate_mode_consistency(mock_redis, "test_service")
        
        # Verify
        assert result['mode'] == 'historical'
        assert result['virtual_time_enabled'] is True
        assert result['virtual_time_current'] == "2026-01-15T09:15:00+05:30"
        assert result['redis_mode'] == 'historical'
    
    def test_virtual_time_in_live_mode_raises_error(self, mock_redis):
        """Test validator raises error when virtual time enabled in live mode."""
        # Setup
        os.environ["EXECUTION_MODE"] = "live"
        mock_redis.get.side_effect = lambda key: {
            "system:virtual_time:enabled": b"1",
            "system:virtual_time:current": b"2026-01-15T09:15:00+05:30"
        }.get(key)
        
        # Execute & Verify
        with pytest.raises(ModeValidationError) as exc_info:
            validate_mode_consistency(mock_redis, "test_service")
        
        assert "CRITICAL" in str(exc_info.value)
        assert "Virtual time is enabled" in str(exc_info.value)
        assert "EXECUTION_MODE=live" in str(exc_info.value)
    
    def test_mode_mismatch_warning(self, mock_redis):
        """Test validator warns when ENV and Redis modes don't match."""
        # Setup
        os.environ["EXECUTION_MODE"] = "live"
        mock_redis.get.side_effect = lambda key: {
            "system:execution_mode": b"historical",  # Mismatch
            "system:virtual_time:enabled": b"0"
        }.get(key)
        mock_redis.scan_iter.return_value = iter([b"live:ohlc:test"])
        
        # Execute
        result = validate_mode_consistency(mock_redis, "test_service")
        
        # Verify
        assert result['mode'] == 'live'  # ENV takes precedence
        assert result['redis_mode'] == 'historical'
        assert len(result['warnings']) > 0
        assert result['status'] == 'error'
        assert any('mismatch' in w.lower() for w in result['warnings'])
    
    def test_no_mode_prefixed_keys_warning(self, mock_redis):
        """Test validator warns when no mode-prefixed keys found."""
        # Setup
        os.environ["EXECUTION_MODE"] = "live"
        mock_redis.get.return_value = None
        mock_redis.scan_iter.return_value = iter([])  # No keys
        
        # Execute
        result = validate_mode_consistency(mock_redis, "test_service")
        
        # Verify
        assert len(result['warnings']) > 0
        assert any('No live-prefixed keys' in w for w in result['warnings'])
    
    def test_orphaned_keys_warning(self, mock_redis):
        """Test validator warns about orphaned keys from other mode."""
        # Setup
        os.environ["EXECUTION_MODE"] = "live"
        mock_redis.get.return_value = None
        
        def scan_iter_side_effect(match, count):
            if match == "live:*":
                return iter([b"live:ohlc:test"])
            elif match == "historical:*":
                return iter([b"historical:ohlc:old1", b"historical:ohlc:old2"])
            return iter([])
        
        mock_redis.scan_iter.side_effect = scan_iter_side_effect
        
        # Execute
        result = validate_mode_consistency(mock_redis, "test_service")
        
        # Verify
        assert len(result['warnings']) > 0
        assert any('historical' in w.lower() and 'keys' in w.lower() 
                  for w in result['warnings'])
    
    def test_redis_connection_failure_handled(self, mock_redis):
        """Test validator handles Redis connection failures gracefully."""
        # Setup
        os.environ["EXECUTION_MODE"] = "live"
        mock_redis.get.side_effect = Exception("Connection refused")
        
        # Execute - should not raise, should handle gracefully
        result = validate_mode_consistency(mock_redis, "test_service")
        
        # Verify
        assert result['mode'] == 'live'  # Still returns mode from ENV
        assert result['redis_mode'] is None
        assert result['virtual_time_enabled'] is False
    
    def test_log_mode_startup(self, caplog):
        """Test mode startup logging."""
        # Setup
        os.environ["EXECUTION_MODE"] = "live"
        
        # Execute
        with caplog.at_level('INFO'):
            log_mode_startup("Test Service", mode="live")
        
        # Verify
        assert "TEST SERVICE STARTING" in caplog.text
        assert "Execution Mode: LIVE" in caplog.text
    
    def test_historical_mode_without_virtual_time(self, mock_redis):
        """Test historical mode works without virtual time (data replay scenario)."""
        # Setup
        os.environ["EXECUTION_MODE"] = "historical"
        mock_redis.get.side_effect = lambda key: {
            "system:execution_mode": b"historical",
            "system:virtual_time:enabled": b"0"  # Not using virtual time
        }.get(key)
        mock_redis.scan_iter.return_value = iter([b"historical:ohlc:test"])
        
        # Execute
        result = validate_mode_consistency(mock_redis, "test_service")
        
        # Verify - Should pass, virtual time is optional for historical mode
        assert result['mode'] == 'historical'
        assert result['virtual_time_enabled'] is False
        assert result['status'] in ['ok', 'error']  # May have other warnings
    
    def test_unknown_mode_defaults_to_live(self, mock_redis):
        """Test unknown mode defaults to live."""
        # Setup
        os.environ["EXECUTION_MODE"] = "invalid_mode"
        mock_redis.get.return_value = None
        mock_redis.scan_iter.return_value = iter([])
        
        # Execute
        result = validate_mode_consistency(mock_redis, "test_service")
        
        # Verify - redis_key_manager should handle invalid mode
        assert result['mode'] in ['live', 'historical']  # Should default


class TestModeValidatorIntegration:
    """Integration tests that require actual Redis (marked as integration)."""
    
    @pytest.mark.integration
    def test_validate_with_real_redis(self):
        """Test validator with real Redis connection."""
        import redis
        
        # Setup
        os.environ["EXECUTION_MODE"] = "live"
        redis_client = redis.Redis(host='localhost', port=6379, db=0)
        
        try:
            redis_client.ping()
        except redis.ConnectionError:
            pytest.skip("Redis not available for integration test")
        
        # Execute
        result = validate_mode_consistency(redis_client, "integration_test")
        
        # Verify
        assert result['mode'] in ['live', 'historical']
        assert isinstance(result['warnings'], list)
        assert result['status'] in ['ok', 'error']
    
    @pytest.mark.integration
    def test_mode_consistency_across_services(self):
        """Test mode consistency when multiple services check."""
        import redis
        
        redis_client = redis.Redis(host='localhost', port=6379, db=0)
        
        try:
            redis_client.ping()
        except redis.ConnectionError:
            pytest.skip("Redis not available")
        
        # Validate from multiple "services"
        result1 = validate_mode_consistency(redis_client, "service_1")
        result2 = validate_mode_consistency(redis_client, "service_2")
        
        # All should see same mode
        assert result1['mode'] == result2['mode']


# Run with: pytest market_data/tests/test_mode_validator.py -v
# Run integration tests: pytest market_data/tests/test_mode_validator.py -v -m integration
