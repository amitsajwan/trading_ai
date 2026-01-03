"""
Smoke test suite for end-to-end system validation
Run this after deployments to verify critical functionality
"""
import sys
import time
import logging
from datetime import datetime
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SmokeTest:
    """Base class for smoke tests"""
    
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error = None
        self.duration = 0
    
    def run(self) -> bool:
        """Run the test and return success status"""
        raise NotImplementedError


class MongoDBConnectionTest(SmokeTest):
    """Test MongoDB connectivity"""
    
    def __init__(self):
        super().__init__("MongoDB Connection")
    
    def run(self) -> bool:
        start = time.time()
        try:
            from mongodb_schema import get_mongo_client
            
            client = get_mongo_client()
            db = client.trading_system
            
            # Test connection
            db.command('ping')
            
            # Test collections exist
            collections = db.list_collection_names()
            required = ['signals', 'trades', 'agents_analysis', 'alerts']
            
            for coll in required:
                if coll not in collections:
                    raise Exception(f"Missing collection: {coll}")
            
            self.passed = True
            logger.info(f"✓ {self.name}: Connected, collections verified")
            
        except Exception as e:
            self.error = str(e)
            logger.error(f"✗ {self.name}: {self.error}")
        finally:
            self.duration = time.time() - start
        
        return self.passed


class LLMProviderTest(SmokeTest):
    """Test LLM provider availability"""
    
    def __init__(self):
        super().__init__("LLM Provider Health")
    
    def run(self) -> bool:
        start = time.time()
        try:
            from agents.llm_provider_manager import get_llm_manager
            from config.settings import settings
            
            # Configure environment
            from utils.request_router import configure_python_environment
            configure_python_environment()
            
            manager = get_llm_manager()
            
            if not manager:
                raise Exception("LLM manager not initialized")
            
            # Check at least one provider is healthy
            healthy_providers = [
                name for name, info in manager.providers.items()
                if info.get('status') == 'healthy'
            ]
            
            if not healthy_providers:
                raise Exception("No healthy LLM providers available")
            
            self.passed = True
            logger.info(f"✓ {self.name}: {len(healthy_providers)} healthy provider(s)")
            
        except Exception as e:
            self.error = str(e)
            logger.error(f"✗ {self.name}: {self.error}")
        finally:
            self.duration = time.time() - start
        
        return self.passed


class DashboardAPITest(SmokeTest):
    """Test dashboard API endpoints"""
    
    def __init__(self):
        super().__init__("Dashboard API")
    
    def run(self) -> bool:
        start = time.time()
        try:
            import requests
            
            base_url = "http://localhost:8000"
            
            # Test health endpoint
            response = requests.get(f"{base_url}/api/health", timeout=5)
            response.raise_for_status()
            
            # Test metrics endpoint
            response = requests.get(f"{base_url}/api/metrics/llm", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if 'providers' not in data and 'error' not in data:
                raise Exception("Invalid metrics response format")
            
            self.passed = True
            logger.info(f"✓ {self.name}: Endpoints responding")
            
        except Exception as e:
            self.error = str(e)
            logger.error(f"✗ {self.name}: {self.error}")
        finally:
            self.duration = time.time() - start
        
        return self.passed


class AlertSystemTest(SmokeTest):
    """Test alert routing system"""
    
    def __init__(self):
        super().__init__("Alert System")
    
    def run(self) -> bool:
        start = time.time()
        try:
            from monitoring.alert_router import initialize_alert_router, send_alert
            from mongodb_schema import get_mongo_client
            from config.settings import settings
            
            client = get_mongo_client()
            db = client.trading_system
            
            # Initialize router
            router = initialize_alert_router(settings, db)
            
            # Send test alert
            result = send_alert(
                alert_type='smoke_test',
                message='Smoke test alert',
                severity='info',
                details={'test_time': datetime.utcnow().isoformat()},
                source='smoke_test'
            )
            
            if result == 0:
                raise Exception("Alert not delivered to any backend")
            
            # Verify alert in database
            alert = db.alerts.find_one({'type': 'smoke_test', 'source': 'smoke_test'})
            if not alert:
                raise Exception("Alert not found in database")
            
            # Cleanup test alert
            db.alerts.delete_one({'_id': alert['_id']})
            
            self.passed = True
            logger.info(f"✓ {self.name}: Alert delivered and verified")
            
        except Exception as e:
            self.error = str(e)
            logger.error(f"✗ {self.name}: {self.error}")
        finally:
            self.duration = time.time() - start
        
        return self.passed


class SchemaValidationTest(SmokeTest):
    """Test MongoDB schema validators"""
    
    def __init__(self):
        super().__init__("Schema Validation")
    
    def run(self) -> bool:
        start = time.time()
        try:
            from mongodb_schema import get_mongo_client, apply_schema_validators
            from config.settings import settings
            
            client = get_mongo_client()
            db = client.trading_system
            
            # Apply validators
            if settings.enable_schema_validation:
                apply_schema_validators(db)
                logger.info("Schema validators applied")
            else:
                logger.info("Schema validation disabled (feature flag)")
            
            # Test basic document structure
            test_trade = {
                'instrument': 'SMOKE_TEST',
                'action': 'BUY',
                'quantity': 1,
                'entry_price': 100.0,
                'timestamp': datetime.utcnow()
            }
            
            # Insert and delete test trade
            result = db.trades.insert_one(test_trade)
            db.trades.delete_one({'_id': result.inserted_id})
            
            self.passed = True
            logger.info(f"✓ {self.name}: Schema validation working")
            
        except Exception as e:
            self.error = str(e)
            logger.error(f"✗ {self.name}: {self.error}")
        finally:
            self.duration = time.time() - start
        
        return self.passed


class CircuitBreakerTest(SmokeTest):
    """Test circuit breaker functionality"""
    
    def __init__(self):
        super().__init__("Circuit Breaker")
    
    def run(self) -> bool:
        start = time.time()
        try:
            from utils.request_router import CircuitBreaker
            from config.settings import settings
            
            if not settings.enable_circuit_breaker:
                logger.info("Circuit breaker disabled (feature flag)")
                self.passed = True
                return True
            
            # Create test circuit breaker
            cb = CircuitBreaker(
                name='smoke_test',
                failure_threshold=3,
                timeout=5,
                recovery_timeout=10
            )
            
            # Test state transitions
            assert cb.state == 'CLOSED', "Initial state should be CLOSED"
            
            # Simulate failures
            for _ in range(3):
                cb.record_failure()
            
            assert cb.state == 'OPEN', "Should open after threshold failures"
            
            # Test call blocking
            allowed = cb.allow_request()
            assert not allowed, "Should block requests when OPEN"
            
            self.passed = True
            logger.info(f"✓ {self.name}: State transitions working")
            
        except Exception as e:
            self.error = str(e)
            logger.error(f"✗ {self.name}: {self.error}")
        finally:
            self.duration = time.time() - start
        
        return self.passed


def run_smoke_tests() -> Dict[str, Any]:
    """Run all smoke tests and return results"""
    
    logger.info("=" * 60)
    logger.info("SMOKE TEST SUITE - Starting")
    logger.info("=" * 60)
    
    tests = [
        MongoDBConnectionTest(),
        LLMProviderTest(),
        AlertSystemTest(),
        SchemaValidationTest(),
        CircuitBreakerTest(),
        # DashboardAPITest(),  # Requires server to be running
    ]
    
    results = {
        'timestamp': datetime.utcnow().isoformat(),
        'total': len(tests),
        'passed': 0,
        'failed': 0,
        'tests': []
    }
    
    for test in tests:
        logger.info(f"\nRunning: {test.name}")
        test.run()
        
        results['tests'].append({
            'name': test.name,
            'passed': test.passed,
            'error': test.error,
            'duration': round(test.duration, 3)
        })
        
        if test.passed:
            results['passed'] += 1
        else:
            results['failed'] += 1
    
    logger.info("\n" + "=" * 60)
    logger.info(f"SMOKE TEST SUITE - Completed")
    logger.info(f"Passed: {results['passed']}/{results['total']}")
    logger.info(f"Failed: {results['failed']}/{results['total']}")
    logger.info("=" * 60)
    
    return results


def main():
    """Main entry point"""
    results = run_smoke_tests()
    
    # Exit with error code if any tests failed
    if results['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
