"""Test script to verify scenario path generation and learning agent prompt updates."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.portfolio_manager import PortfolioManagerAgent
from agents.learning_agent import LearningAgent
from agents.state import AgentState


def test_scenario_paths():
    """Test scenario path generation."""
    print("=" * 60)
    print("Testing Scenario Path Generation")
    print("=" * 60)
    
    # Create portfolio manager
    pm = PortfolioManagerAgent()
    
    # Mock data for testing
    current_price = 60000.0
    technical = {
        "trend_direction": "UP",
        "trend_strength": 65.0,
        "support_level": 59500.0,
        "resistance_level": 60500.0,
        "atr": 300.0,
        "rsi": 55.0,
        "rsi_status": "NEUTRAL"
    }
    fundamental = {
        "sector_strength": "MODERATE",
        "bullish_probability": 0.6,
        "bearish_probability": 0.4,
        "key_catalysts": ["Strong earnings", "Positive sector trend"],
        "key_risk_factors": ["Macro headwinds", "High valuations"]
    }
    sentiment = {
        "retail_sentiment": 0.3,
        "institutional_sentiment": 0.2,
        "sentiment_divergence": "NONE"
    }
    macro = {
        "macro_regime": "RISK_ON",
        "sector_headwind_score": 0.1
    }
    
    bull_thesis = "Strong technical setup with breakout above resistance. Positive fundamental catalysts."
    bear_thesis = "Overbought conditions and macro headwinds could trigger pullback."
    bull_confidence = 0.65
    bear_confidence = 0.45
    
    # Generate scenarios
    scenarios = pm._generate_scenario_paths(
        current_price, technical, fundamental, sentiment, macro,
        bull_thesis, bear_thesis, bull_confidence, bear_confidence
    )
    
    print("\n✅ Scenario Paths Generated Successfully!")
    print("\n📊 BASE CASE:")
    print(f"  Target (15m): ${scenarios['base_case']['target_15m']:,.2f}")
    print(f"  Target (60m): ${scenarios['base_case']['target_60m']:,.2f}")
    print(f"  Probability: {scenarios['base_case']['probability']:.0%}")
    print(f"  Description: {scenarios['base_case']['description']}")
    
    print("\n🟢 BULL CASE:")
    print(f"  Target (15m): ${scenarios['bull_case']['target_15m']:,.2f}")
    print(f"  Target (60m): ${scenarios['bull_case']['target_60m']:,.2f}")
    print(f"  Probability: {scenarios['bull_case']['probability']:.0%}")
    print(f"  Catalysts: {', '.join(scenarios['bull_case']['catalysts'])}")
    
    print("\n🔴 BEAR CASE:")
    print(f"  Target (15m): ${scenarios['bear_case']['target_15m']:,.2f}")
    print(f"  Target (60m): ${scenarios['bear_case']['target_60m']:,.2f}")
    print(f"  Probability: {scenarios['bear_case']['probability']:.0%}")
    print(f"  Catalysts: {', '.join(scenarios['bear_case']['catalysts'])}")
    
    print("\n📈 VOLATILITY RANGE:")
    print(f"  ATR: ${scenarios['volatility_range']['atr']:,.2f}")
    print(f"  Expected Range (15m): ${scenarios['volatility_range']['expected_range_15m'][0]:,.2f} - ${scenarios['volatility_range']['expected_range_15m'][1]:,.2f}")
    print(f"  Expected Range (60m): ${scenarios['volatility_range']['expected_range_60m'][0]:,.2f} - ${scenarios['volatility_range']['expected_range_60m'][1]:,.2f}")
    
    return True


def test_learning_agent():
    """Test learning agent prompt update capability."""
    print("\n" + "=" * 60)
    print("Testing Learning Agent Prompt Updates")
    print("=" * 60)
    
    learning = LearningAgent()
    
    # Mock insights with poor performance
    mock_insights = {
        "total_trades": 10,
        "win_rate": 35.0,  # Low win rate
        "agent_accuracy": {
            "technical": 40.0,  # Below threshold
            "fundamental": 55.0,
            "sentiment": 38.0,  # Below threshold
            "macro": 60.0
        },
        "average_pnl": -150.0
    }
    
    print("\n📊 Mock Performance Data:")
    print(f"  Win Rate: {mock_insights['win_rate']:.1f}%")
    print(f"  Agent Accuracies:")
    for agent, acc in mock_insights['agent_accuracy'].items():
        print(f"    - {agent}: {acc:.1f}%")
    
    # Test prompt update (with auto_update=False for testing)
    print("\n🔄 Testing Prompt Update Logic (dry run)...")
    try:
        updated = learning.update_prompts_from_performance(
            mock_insights, auto_update=False  # Dry run
        )
        print(f"✅ Prompt update logic works! Would update {len(updated)} agents.")
        print(f"  Agents to update: {', '.join(updated.keys()) if updated else 'None'}")
        return True
    except Exception as e:
        print(f"❌ Error testing prompt updates: {e}")
        return False


if __name__ == "__main__":
    print("\n🚀 Starting Validation Tests...\n")
    
    # Test scenario paths
    scenario_ok = test_scenario_paths()
    
    # Test learning agent
    learning_ok = test_learning_agent()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"✅ Scenario Paths: {'PASS' if scenario_ok else 'FAIL'}")
    print(f"✅ Learning Agent: {'PASS' if learning_ok else 'FAIL'}")
    
    if scenario_ok and learning_ok:
        print("\n🎉 All tests passed! Code is ready.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Review errors above.")
        sys.exit(1)
