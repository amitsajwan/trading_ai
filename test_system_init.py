"""Simple system initialization test."""

import sys
import os

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from agents.state import AgentState, SignalType
        print("✓ AgentState imported")
        
        from agents.base_agent import BaseAgent
        print("✓ BaseAgent imported")
        
        from config.settings import TradingConfig
        print("✓ TradingConfig imported")
        
        from data.market_memory import MarketMemory
        print("✓ MarketMemory imported")
        
        from utils.paper_trading import PaperTrading
        print("✓ PaperTrading imported")
        
        from monitoring.circuit_breakers import CircuitBreaker
        print("✓ CircuitBreaker imported")
        
        print("\n✅ All core modules imported successfully!")
        return True
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        return False


def test_agent_state():
    """Test AgentState creation."""
    print("\nTesting AgentState...")
    
    try:
        from agents.state import AgentState, SignalType
        from datetime import datetime
        
        state = AgentState(
            current_price=45000.0,
            current_time=datetime.now()
        )
        
        assert state.current_price == 45000.0
        assert state.final_signal == SignalType.HOLD
        
        print("✓ AgentState created successfully")
        return True
    except Exception as e:
        print(f"❌ AgentState test failed: {e}")
        return False


def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    
    try:
        from config.settings import TradingConfig
        
        # Set test env vars
        os.environ["KITE_API_KEY"] = "test_key"
        os.environ["PAPER_TRADING_MODE"] = "true"
        
        config = TradingConfig.from_env()
        
        assert config.kite_api_key == "test_key"
        assert config.paper_trading_mode == True
        
        print("✓ Configuration loaded successfully")
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_paper_trading():
    """Test paper trading."""
    print("\nTesting paper trading...")
    
    try:
        from utils.paper_trading import PaperTrading
        
        paper = PaperTrading(initial_capital=1000000)
        
        assert paper.initial_capital == 1000000
        assert paper.current_capital == 1000000
        
        print("✓ PaperTrading initialized successfully")
        return True
    except Exception as e:
        print(f"❌ PaperTrading test failed: {e}")
        return False


def main():
    """Run all system tests."""
    print("=" * 60)
    print("GenAI Trading System - Initialization Test")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("AgentState", test_agent_state()))
    results.append(("Configuration", test_config()))
    results.append(("Paper Trading", test_paper_trading()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary:")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:20} {status}")
    
    all_passed = all(result for _, result in results)
    
    print("=" * 60)
    if all_passed:
        print("✅ All system initialization tests passed!")
        print("\nSystem is ready for testing. Next steps:")
        print("1. Set up MongoDB and Redis")
        print("2. Configure .env file with API keys")
        print("3. Run: python trading_orchestration/main.py")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

