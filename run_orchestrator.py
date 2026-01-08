"""Run the orchestrator continuously to generate real agent discussions."""
import asyncio
import logging
import sys
import os
import random
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional dependency
    np = None

# Import time service for virtual/historical time support
try:
    from core_kernel.src.core_kernel.time_service import now as get_system_time
except ImportError:
    # Fallback if time service not available
    def get_system_time() -> datetime:
        return datetime.now()

# Import market hours checker
try:
    from core_kernel.src.core_kernel.market_hours import is_market_open
except ImportError:
    # Fallback - always return True if module not available
    def is_market_open(now: datetime = None) -> bool:
        return True

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add module paths for local packages
PROJECT_ROOT = os.path.dirname(__file__)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "engine_module", "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "genai_module", "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "data_niftybank", "src"))


class StubMarketStore:
    """Async-friendly market store returning synthetic data."""

    async def get_latest_ticks(self, instrument: str, limit: int = 100):
        price = 48500 + random.uniform(-150, 150)
        tick = SimpleNamespace(last_price=price, timestamp=get_system_time().isoformat())
        return [tick]

    async def get_ohlc_data(self, symbol: str, periods: int = 100) -> list[dict]:
        """Get OHLC data for technical analysis."""
        bars = []
        base_price = 48000
        timestamp = get_system_time() - timedelta(minutes=15 * periods)
        for _ in range(periods):
            drift = random.uniform(-30, 30)
            open_price = base_price + drift
            close_price = open_price + random.uniform(-40, 40)
            high = max(open_price, close_price) + random.uniform(5, 25)
            low = min(open_price, close_price) - random.uniform(5, 25)
            bars.append({
                "timestamp": timestamp.isoformat(),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close_price, 2),
                "volume": int(18_000_000 + random.uniform(-2_000_000, 2_000_000)),
            })
            timestamp += timedelta(minutes=15)
        return bars

    async def get_ohlc(self, instrument: str, timeframe: str, start=None, end=None):
        bars = []
        base_price = 48000
        period_count = 96  # 24 hours of 15m bars
        timestamp = get_system_time() - timedelta(minutes=15 * period_count)
        for _ in range(period_count):
            drift = random.uniform(-30, 30)
            open_price = base_price + drift
            close_price = open_price + random.uniform(-40, 40)
            high = max(open_price, close_price) + random.uniform(5, 25)
            low = min(open_price, close_price) - random.uniform(5, 25)
            bars.append({
                "timestamp": timestamp.isoformat(),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close_price, 2),
                "volume": int(18_000_000 + random.uniform(-2_000_000, 2_000_000)),
            })
            timestamp += timedelta(minutes=15)
        return bars


class StubOptionsClient:
    """Minimal options client when real Zerodha client isn't configured."""

    async def fetch_chain(self, instrument: str, expiry: str | None = None) -> Dict[str, Any]:
        """Return placeholder chain so orchestrator can continue running."""
        strikes = [int(48000 + i * 100) for i in range(-3, 4)]
        calls = [{"strike": s, "price": round(max(10, 150 - abs(48000 - s) * 0.5), 2), "oi": 100000 + i * 5000}
                 for i, s in enumerate(strikes)]
        puts = [{"strike": s, "price": round(max(10, 140 - abs(48000 - s) * 0.45), 2), "oi": 90000 + i * 4000}
                for i, s in enumerate(strikes)]
        return {
            "instrument": instrument,
            "expiries": ["2026-01-08", "2026-01-15"],
            "calls": calls,
            "puts": puts,
            "underlying_price": 48500.0,
            "pcr": round(sum(p["oi"] for p in puts) / max(1, sum(c["oi"] for c in calls)), 2),
            "max_pain": 48500,
        }


NUMPY_SCALARS = (np.generic,) if np is not None else tuple()
NUMPY_ARRAYS = (np.ndarray,) if np is not None else tuple()
AGG_SIGNAL_BUCKETS = [
    "technical_signals",
    "sentiment_signals",
    "macro_signals",
    "risk_signals",
    "execution_signals",
    "bull_bear_signals",
]


def _sanitize_for_bson(value):
    """Recursively convert numpy/scalar types so Mongo can persist them."""
    if isinstance(value, dict):
        return {str(k): _sanitize_for_bson(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_bson(v) for v in value]
    if isinstance(value, tuple):
        return [_sanitize_for_bson(v) for v in value]
    if isinstance(value, set):
        return [_sanitize_for_bson(v) for v in value]
    if NUMPY_SCALARS and isinstance(value, NUMPY_SCALARS):
        return value.item()
    if NUMPY_ARRAYS and isinstance(value, NUMPY_ARRAYS):
        return value.tolist()
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float, bool, str)) or value is None:
        return value
    # Fallback to string representation for unsupported objects
    return str(value)


def _extract_agent_signals(details: Dict[str, Any] | None) -> list[Dict[str, Any]]:
    """Flatten agent signals from orchestrator result details."""
    if not isinstance(details, dict):
        return []

    direct_signals = details.get("agent_signals")
    if isinstance(direct_signals, list):
        return direct_signals
    if isinstance(direct_signals, dict):
        return list(direct_signals.values())

    aggregated = details.get("aggregated_analysis")
    if not isinstance(aggregated, dict):
        return []

    flattened: list[Dict[str, Any]] = []
    for bucket in AGG_SIGNAL_BUCKETS:
        entries = aggregated.get(bucket, [])
        if isinstance(entries, dict):
            entries = list(entries.values())
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                flattened.append(entry)
    return flattened


async def run_continuous_orchestrator():
    """Run orchestrator in continuous mode, writing to MongoDB."""
    
    print("=" * 80)
    print("STARTING ORCHESTRATOR - CONTINUOUS MODE")
    print("=" * 80)
    print()
    
    try:
        # Import dependencies
        from engine_module.agent_factory import create_default_agents
        from engine_module.api import build_orchestrator
        from genai_module.core.llm_provider_manager import LLMProviderManager
        from genai_module.api import build_llm_client
        
        # Use async-friendly stubs for market/options data when real pipelines aren't configured
        market_store = StubMarketStore()
        print("✅ Using stub market store (synthetic OHLC/ticks)")

        options_client = StubOptionsClient()
        print("✅ Using stub options chain client")
        
        # Initialize news service (optional - will work without it)
        news_service = None
        try:
            from core_kernel.src.core_kernel.mongodb_schema import get_db_connection
            from news_module.api import build_news_service
            
            # Get MongoDB connection for news storage
            db = get_db_connection()
            news_collection = db["news"]
            news_service = build_news_service(news_collection)
            print("✅ News service initialized with MongoDB storage")
        except Exception as e:
            print(f"⚠️  News service not available: {e}")
            print("   Orchestrator will run without news sentiment analysis")
        
        # Create LLM client with real provider manager
        llm_manager = LLMProviderManager()
        llm_client = build_llm_client(llm_manager)
        print(f"✅ LLM client initialized with {len(llm_manager.providers)} providers")
        
        # Create all agents
        agents = create_default_agents(profile='balanced')
        print(f"✅ Created {len(agents)} agents")
        
        # Initialize technical indicators service
        technical_data_provider = None
        try:
            from engine_module.services.technical_indicators_service import TechnicalIndicatorsService
            technical_data_provider = TechnicalIndicatorsService(market_store)
            print("✅ Technical indicators service initialized")
        except Exception as e:
            print(f"⚠️  Technical indicators service not available: {e}")
            print("   Agents will calculate indicators individually")
        
        # Build orchestrator
        orchestrator = build_orchestrator(
            llm_client=llm_client,
            market_store=market_store,
            options_data=options_client,
            news_service=news_service,
            technical_data_provider=technical_data_provider,
            agents=agents,
            instrument="BANKNIFTY"
        )
        print("✅ Orchestrator built successfully")
        print()
        
        # Get current mode and use appropriate database for persistence
        from core_kernel.src.core_kernel.mode_manager import get_mode_manager
        
        # Get current mode and use appropriate database
        mode_manager = get_mode_manager()
        current_mode = mode_manager.get_current_mode()
        db = get_db_connection(mode=current_mode)
        print(f"✅ Using database: {get_db_connection(mode=current_mode).name} (mode: {current_mode})")
        
        # Run cycles
        cycle_count = 0
        cycle_interval_seconds = 15 * 60  # 15 minutes
        
        # For demo, run faster (every 2 minutes)
        demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
        if demo_mode:
            cycle_interval_seconds = 120  # 2 minutes
            print("🚀 Running in DEMO mode - 2 minute cycles")
        else:
            print(f"🚀 Running in PRODUCTION mode - {cycle_interval_seconds/60} minute cycles")
        
        print()
        print("Starting continuous analysis cycles... (Press Ctrl+C to stop)")
        print("-" * 80)
        
        while True:
            cycle_count += 1
            cycle_start = get_system_time()  # Use virtual time if available
            
            # Check if market is open (skip when explicitly forced)
            force_market_open = os.environ.get('FORCE_MARKET_OPEN', 'false').lower() == 'true'
            simulation_mode = os.environ.get('SIMULATION_MODE', 'false').lower() == 'true'
            market_open = force_market_open or simulation_mode or is_market_open(cycle_start)
            
            if not market_open:
                print(f"\n[{cycle_start.strftime('%H:%M:%S')}] 🛑 Market is CLOSED - Skipping cycle #{cycle_count}")
                print(f"   Market hours: Monday-Friday, 9:15 AM - 3:30 PM IST")
                print(f"   Current day: {cycle_start.strftime('%A')}, Time: {cycle_start.strftime('%H:%M:%S')}")
                print(f"   Agents and LLM calls paused until market opens...")
                # Wait and check again
                await asyncio.sleep(60)  # Check every minute
                continue
            
            print(f"\n[{cycle_start.strftime('%H:%M:%S')}] 🔄 Cycle #{cycle_count} starting...")
            
            try:
                context = {
                    "instrument": "BANKNIFTY",
                    "timestamp": cycle_start,
                    "market_hours": market_open,
                    "cycle_interval": "15min",
                    "cycle_number": cycle_count
                }
                
                # Run orchestrator cycle
                result = await orchestrator.run_cycle(context)

                # Normalize details for persistence
                result_details = result.details if isinstance(result.details, dict) else {}
                agent_signal_entries = _extract_agent_signals(result_details)
                reasoning_text = result_details.get("reasoning")
                if not reasoning_text:
                    agg = result_details.get("aggregated_analysis", {})
                    insights = agg.get("key_insights", [])
                    reasoning_text = insights[0] if insights else ""

                # Save to MongoDB
                decision_doc = _sanitize_for_bson({
                    "timestamp": cycle_start.isoformat(),
                    "cycle_number": cycle_count,
                    "instrument": "BANKNIFTY",
                    "final_signal": result.decision,
                    "confidence": result.confidence,
                    "reasoning": reasoning_text,
                    "details": result_details,
                    "agent_count": len(agent_signal_entries)
                })
                db.agent_decisions.insert_one(decision_doc)

                # Save individual agent discussions (using mode-aware database)
                for entry in agent_signal_entries:
                    agent_name = entry.get("agent") or entry.get("agent_full_name") or "Unknown Agent"
                    discussion_doc = _sanitize_for_bson({
                        "timestamp": cycle_start.isoformat(),
                        "cycle_number": cycle_count,
                        "agent_name": agent_name,
                        "signal": entry.get("signal", entry.get("decision", "HOLD")),
                        "confidence": entry.get("confidence", 0.0),
                        "weight": entry.get("weight"),
                        "weighted_vote": entry.get("weighted_vote"),
                        "reasoning": entry.get("reasoning"),
                        "indicators": entry.get("indicators") or entry.get("details", {}),
                        "details": entry,
                        "mode": current_mode,  # Track mode for data isolation
                        "instrument": "BANKNIFTY"  # Track instrument for data isolation
                    })
                    db.agent_discussions.insert_one(discussion_doc)
                
                elapsed = (get_system_time() - cycle_start).total_seconds()
                print(f"✅ Cycle #{cycle_count} complete in {elapsed:.1f}s - Decision: {result.decision} ({result.confidence:.0%})")
                
                # Wait for next cycle
                wait_time = max(1, cycle_interval_seconds - elapsed)
                print(f"   Waiting {wait_time:.0f}s until next cycle...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error in cycle #{cycle_count}: {e}", exc_info=True)
                print(f"❌ Cycle #{cycle_count} failed: {e}")
                print("   Waiting 30s before retry...")
                await asyncio.sleep(30)
                
    except KeyboardInterrupt:
        print("\n\n⏹️  Orchestrator stopped by user")
        print(f"Total cycles completed: {cycle_count}")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("\n🤖 Multi-Agent Trading Orchestrator")
    print("   Generates real agent discussions and trading decisions")
    print("   Data saved to MongoDB for dashboard display\n")
    
    asyncio.run(run_continuous_orchestrator())

