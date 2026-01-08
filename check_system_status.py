"""Check system status - LLM providers, agent discussions, and data freshness."""
import sys
import os
from datetime import datetime, timedelta

# Add paths
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'genai_module', 'src'))

print("=" * 80)
print("SYSTEM STATUS CHECK")
print("=" * 80)

# 1. Check LLM Provider Status
print("\n1. LLM PROVIDER STATUS")
print("-" * 80)
try:
    genai_path = os.path.join(os.path.dirname(__file__), 'genai_module', 'src')
    if genai_path not in sys.path:
        sys.path.insert(0, genai_path)
    from genai_module.core.llm_provider_manager import LLMProviderManager
    manager = LLMProviderManager()
    
    if manager.providers:
        print(f"Total providers configured: {len(manager.providers)}")
        print(f"Current provider: {manager.current_provider}")
        print(f"Selection strategy: {manager.selection_strategy}")
        print(f"\nProvider details (sorted by priority):")
        for name, config in sorted(manager.providers.items(), key=lambda x: x[1].priority):
            print(f"  • {name:12} | Status: {config.status.value:12} | Priority: {config.priority} | Model: {config.model}")
            if config.last_error:
                print(f"             └─> Last error: {config.last_error}")
    else:
        print("❌ NO PROVIDERS CONFIGURED")
except Exception as e:
    print(f"❌ ERROR checking LLM providers: {e}")

# 2. Check MongoDB Collections
print("\n2. MONGODB DATA STATUS")
print("-" * 80)
try:
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
    db = client.zerodha_trading
    
    collections = db.list_collection_names()
    print(f"Collections found: {collections}")
    
    # Check each relevant collection
    for coll_name in ["agent_decisions", "agent_discussions", "paper_trades", "llm_calls"]:
        if coll_name in collections:
            coll = db[coll_name]
            count = coll.count_documents({})
            latest = coll.find_one(sort=[("timestamp", -1)])
            
            if latest:
                ts = latest.get("timestamp")
                if isinstance(ts, str):
                    try:
                        ts_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        age = datetime.now() - ts_dt.replace(tzinfo=None)
                        age_str = f"{age.total_seconds():.0f}s ago"
                        if age.total_seconds() > 3600:
                            age_str = f"{age.total_seconds()/3600:.1f}h ago"
                    except:
                        age_str = "unknown age"
                else:
                    age_str = "no timestamp"
                
                print(f"  • {coll_name:20} | Count: {count:5} | Latest: {age_str}")
            else:
                print(f"  • {coll_name:20} | Count: {count:5} | Latest: EMPTY")
        else:
            print(f"  • {coll_name:20} | NOT FOUND")
    
    # Check for agent discussions specifically
    print("\n  Recent Agent Discussions:")
    if "agent_discussions" in collections:
        docs = list(db.agent_discussions.find().sort("timestamp", -1).limit(5))
        if docs:
            for i, doc in enumerate(docs, 1):
                agent = doc.get("agent_name", "Unknown")
                ts = doc.get("timestamp", "no timestamp")
                signal = doc.get("signal", "?")
                print(f"    {i}. [{ts[:19] if isinstance(ts, str) else ts}] {agent}: {signal}")
        else:
            print("    ❌ NO AGENT DISCUSSIONS FOUND - This means agents aren't running!")
    else:
        print("    ❌ Collection 'agent_discussions' doesn't exist - Agents never ran!")
        
except Exception as e:
    print(f"❌ MongoDB error: {e}")

# 3. Check Trading Mode
print("\n3. TRADING CONFIGURATION")
print("-" * 80)
try:
    from dashboard.app import CURRENT_MODE, ALLOWED_INSTRUMENT, PAPER_TRADING_CONFIG
    print(f"Trading Mode: {CURRENT_MODE}")
    print(f"Allowed Instrument: {ALLOWED_INSTRUMENT}")
    print(f"Paper Trading Enabled: {PAPER_TRADING_CONFIG.get('enabled')}")
    print(f"Data Source: {PAPER_TRADING_CONFIG.get('data_source')}")
    
    if CURRENT_MODE == "paper_mock":
        print("\n⚠️  WARNING: Running in MOCK mode - using simulated data!")
    
except Exception as e:
    print(f"Error: {e}")

# 4. Check for running orchestrator/agents
print("\n4. AGENT ORCHESTRATOR STATUS")
print("-" * 80)
try:
    # Check if there's a running orchestrator
    from dashboard.app import TRADING_STATS
    print(f"Cycles Run: {TRADING_STATS.get('cycles_run', 0)}")
    print(f"Signals Generated: {TRADING_STATS.get('signals_generated', 0)}")
    
    if TRADING_STATS.get('cycles_run', 0) == 0:
        print("\n⚠️  NO TRADING CYCLES HAVE RUN - Orchestrator may not be active!")
        print("   The system is showing mock/fallback data only.")
    
except Exception as e:
    print(f"Error: {e}")

# 5. Check environment variables
print("\n5. ENVIRONMENT CONFIGURATION")
print("-" * 80)
from dotenv import load_dotenv
load_dotenv()

important_vars = [
    "TRADING_MODE",
    "LLM_PROVIDER", 
    "LLM_MODEL",
    "GROQ_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "LLM_SELECTION_STRATEGY",
    "SINGLE_PROVIDER",
    "PRIMARY_PROVIDER"
]

for var in important_vars:
    val = os.getenv(var)
    if var.endswith("KEY") and val:
        val = val[:10] + "..." if len(val) > 10 else val
    print(f"  {var:25} = {val or 'NOT SET'}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

# Determine issues
issues = []
recommendations = []

# Check if using SINGLE_PROVIDER mode
if os.getenv("SINGLE_PROVIDER", "false").lower() == "true":
    issues.append("⚠️  Running in SINGLE_PROVIDER mode - only using one provider")
    recommendations.append("Set SINGLE_PROVIDER=false for multi-provider load balancing")

# Check trading mode
if os.getenv("TRADING_MODE", "paper_mock") == "paper_mock":
    issues.append("⚠️  Running in MOCK mode - using fake/simulated data")
    recommendations.append("Set TRADING_MODE=paper_live for real market data")

# Check for agent activity
try:
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
    db = client.zerodha_trading
    agent_count = db.agent_discussions.count_documents({})
    if agent_count == 0:
        issues.append("❌ NO AGENT DISCUSSIONS - Agents are not running!")
        recommendations.append("Start the enhanced orchestrator to run agent analysis")
except:
    pass

if issues:
    print("\n🔍 ISSUES DETECTED:")
    for issue in issues:
        print(f"  {issue}")
    
    print("\n💡 RECOMMENDATIONS:")
    for rec in recommendations:
        print(f"  • {rec}")
else:
    print("\n✅ System appears to be configured correctly")

print("\n" + "=" * 80)

