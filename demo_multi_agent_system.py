"""Demo: Multi-Agent System with Weighted Voting

Demonstrates all 12+ agents working together with:
- Weighted voting (Analysis: 1.5x, Specialists: 1.0x, Research: 0.5x, Risk: 2.0x)
- Risk veto capability
- Bull/Bear researcher contrarian views
- Dynamic consensus calculation
"""

import asyncio
import logging
from datetime import datetime
from pprint import pprint

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def demo_multi_agent_system():
    """Demonstrate the complete multi-agent trading system."""
    
    print("=" * 80)
    print("MULTI-AGENT TRADING SYSTEM DEMO")
    print("=" * 80)
    print()
    
    # Step 1: Create agents using the factory
    print("📦 STEP 1: Creating Agent Roster")
    print("-" * 80)
    
    try:
        from engine_module.agent_factory import create_default_agents, AgentProfile
        
        # Create balanced profile (all agents enabled)
        agents = create_default_agents(profile='balanced')
        
        print(f"✅ Created {len(agents)} agents successfully!")
        for agent in agents:
            agent_name = getattr(agent, '_agent_name', agent.__class__.__name__)
            print(f"   • {agent_name}")
        
    except Exception as e:
        logger.error(f"Failed to create agents: {e}")
        print(f"❌ Error creating agents: {e}")
        return
    
    print()
    
    # Step 2: Build orchestrator with all agents
    print("🎼 STEP 2: Building Orchestrator with All Agents")
    print("-" * 80)
    
    try:
        from engine_module.contracts import build_orchestrator
        from genai_module.stub_llm_client import StubLLMClient
        from market_data.redis_store import RedisMarketStore
        from market_data.options_adapter import StubOptionsClient
        
        # Create dependencies
        llm_client = StubLLMClient()
        market_store = RedisMarketStore()
        options_client = StubOptionsClient()
        
        # Build orchestrator with all agents
        orchestrator = build_orchestrator(
            llm_client=llm_client,
            market_store=market_store,
            options_data=options_client,
            agents=agents,  # Pass all agents
            instrument="BANKNIFTY"
        )
        
        print(f"✅ Orchestrator built with {len(agents)} agents")
        print()
        
    except Exception as e:
        logger.error(f"Failed to build orchestrator: {e}")
        print(f"❌ Error building orchestrator: {e}")
        return
    
    # Step 3: Run analysis cycle
    print("🔄 STEP 3: Running Analysis Cycle")
    print("-" * 80)
    
    try:
        context = {
            "instrument": "BANKNIFTY",
            "timestamp": datetime.now().isoformat(),
            "market_hours": True,
            "cycle_interval": "15min"
        }
        
        print("Running orchestrator cycle...")
        result = await orchestrator.run_cycle(context)
        
        print()
        print("📊 ANALYSIS RESULTS:")
        print("=" * 80)
        print(f"Decision: {result.decision}")
        print(f"Confidence: {result.confidence:.1%}")
        print()
        
        # Extract aggregated analysis
        agg = result.details.get('aggregated_analysis', {})
        
        # Display weighted votes
        print("⚖️  WEIGHTED VOTING RESULTS:")
        print("-" * 80)
        weighted_votes = agg.get('weighted_votes', {})
        print(f"BUY Weight:  {weighted_votes.get('buy', 0):.2f}")
        print(f"SELL Weight: {weighted_votes.get('sell', 0):.2f}")
        print(f"HOLD Weight: {weighted_votes.get('hold', 0):.2f}")
        print()
        
        # Display consensus
        print("🎯 CONSENSUS:")
        print("-" * 80)
        print(f"Direction: {agg.get('consensus_direction', 'N/A')}")
        print(f"Signal Strength: {agg.get('signal_strength', 0):.1%}")
        print(f"Confidence Score: {agg.get('confidence_score', 0):.1%}")
        print(f"Risk Assessment: {agg.get('risk_assessment', 'N/A')}")
        print()
        
        # Check for risk veto
        risk_veto = agg.get('risk_veto', {})
        if risk_veto.get('triggered'):
            print("⚠️  RISK VETO TRIGGERED!")
            print("-" * 80)
            print(f"Reason: {risk_veto.get('reason', 'Unknown')}")
            print()
        
        # Display agent breakdown by category
        print("🤖 AGENT BREAKDOWN:")
        print("-" * 80)
        
        categories = {
            "Analysis Tier (1.5x weight)": agg.get('technical_signals', [])[:4],
            "Technical Specialists (1.0x weight)": agg.get('technical_signals', [])[4:],
            "Research Tier (0.5x weight)": agg.get('bull_bear_signals', []),
            "Risk & Execution": agg.get('risk_signals', []) + agg.get('execution_signals', [])
        }
        
        for category, signals in categories.items():
            if signals:
                print(f"\n{category}:")
                for sig in signals:
                    agent_name = sig.get('agent', 'Unknown')
                    signal = sig.get('signal', 'N/A')
                    confidence = sig.get('confidence', 0)
                    weight = sig.get('weight', 1.0)
                    weighted_vote = sig.get('weighted_vote', 0)
                    
                    print(f"  • {agent_name:20s} {signal:4s} ({confidence:5.1%}) "
                          f"[weight: {weight:.1f}x = {weighted_vote:.2f}]")
        
        print()
        
        # Display key insights
        print("💡 KEY INSIGHTS:")
        print("-" * 80)
        for insight in agg.get('key_insights', []):
            print(f"• {insight}")
        
        print()
        
        # Display options strategy recommendation
        print("📈 OPTIONS STRATEGY:")
        print("-" * 80)
        print(agg.get('options_strategy', 'N/A'))
        print()
        
        print("=" * 80)
        print("✅ DEMO COMPLETED SUCCESSFULLY")
        print("=" * 80)
        
    except Exception as e:
        logger.error(f"Analysis cycle failed: {e}", exc_info=True)
        print(f"❌ Error running analysis: {e}")
        return


async def demo_agent_factory():
    """Demonstrate the agent factory with different profiles."""
    
    print()
    print("=" * 80)
    print("AGENT FACTORY DEMO - Different Profiles")
    print("=" * 80)
    print()
    
    from engine_module.agent_factory import AgentFactory, AgentProfile
    
    profiles = [
        AgentProfile.CONSERVATIVE,
        AgentProfile.BALANCED,
        AgentProfile.AGGRESSIVE,
        AgentProfile.RESEARCH_HEAVY
    ]
    
    for profile in profiles:
        print(f"Profile: {profile.value.upper()}")
        print("-" * 80)
        
        factory = AgentFactory(profile=profile)
        agents = factory.build_all_agents()
        summary = factory.get_agent_summary()
        
        print(f"Total Agents: {summary['total_agents']}")
        print()
        
        for category, agent_names in summary['categories'].items():
            print(f"  {category}: {len(agent_names)}")
            for name in agent_names:
                print(f"    • {name}")
        
        print()


if __name__ == "__main__":
    print()
    print("🚀 Starting Multi-Agent System Demo")
    print()
    
    # Run the main demo
    asyncio.run(demo_multi_agent_system())
    
    # Run the factory demo
    asyncio.run(demo_agent_factory())
    
    print()
    print("Demo completed!")

