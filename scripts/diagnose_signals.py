#!/usr/bin/env python3
"""
Diagnostic Script: Signal Generation System Health Check

This script performs a comprehensive health check of the signal generation system,
verifying each component and identifying why signals may not be generated.

Usage:
    python scripts/diagnose_signals.py
    python scripts/diagnose_signals.py --verbose
    python scripts/diagnose_signals.py --fix-pending  # Clear old pending signals
"""

import os
import sys
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(text: str):
    """Print formatted section header."""
    print(f"\n{BLUE}{BOLD}{'=' * 70}{RESET}")
    print(f"{BLUE}{BOLD}{text:^70}{RESET}")
    print(f"{BLUE}{BOLD}{'=' * 70}{RESET}\n")


def print_check(name: str, status: bool, details: str = ""):
    """Print check result with color coding."""
    icon = f"{GREEN}[OK]{RESET}" if status else f"{RED}[FAIL]{RESET}"
    status_text = f"{GREEN}OK{RESET}" if status else f"{RED}FAIL{RESET}"
    print(f"{icon} {name:.<50} [{status_text}]")
    if details:
        print(f"   {YELLOW}->{RESET} {details}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}WARNING: {text}{RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{BLUE}INFO: {text}{RESET}")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}SUCCESS: {text}{RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}ERROR: {text}{RESET}")


async def check_redis_connection() -> Dict[str, Any]:
    """Check Redis connectivity and data."""
    try:
        import redis
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        
        client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        client.ping()
        
        # Check for recent ticks
        tick_keys = client.keys("market:tick:*")
        indicator_keys = client.keys("indicators:*")
        
        return {
            "connected": True,
            "host": redis_host,
            "port": redis_port,
            "tick_keys": len(tick_keys),
            "indicator_keys": len(indicator_keys)
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


async def check_mongodb_connection() -> Dict[str, Any]:
    """Check MongoDB connectivity and signal collection."""
    try:
        from pymongo import MongoClient
        
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        
        db = client[db_name]
        signals_collection = db['signals']
        
        # Count signals by status
        pending_count = signals_collection.count_documents({"status": "pending", "is_active": True})
        triggered_count = signals_collection.count_documents({"status": "triggered"})
        executed_count = signals_collection.count_documents({"status": "executed"})
        expired_count = signals_collection.count_documents({"status": "expired"})
        
        # Get most recent signal
        recent_signal = signals_collection.find_one(
            {},
            sort=[("created_at", -1)]
        )
        
        return {
            "connected": True,
            "uri": mongo_uri,
            "database": db_name,
            "pending_signals": pending_count,
            "triggered_signals": triggered_count,
            "executed_signals": executed_count,
            "expired_signals": expired_count,
            "most_recent_signal": recent_signal.get("created_at") if recent_signal else None,
            "most_recent_action": recent_signal.get("action") if recent_signal else None
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


async def check_orchestrator_api() -> Dict[str, Any]:
    """Check engine API orchestrator status."""
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Health check
            health_resp = await client.get("http://localhost:8006/health")
            health = health_resp.json() if health_resp.status_code == 200 else {}
            
            return {
                "api_available": health_resp.status_code == 200,
                "health": health,
                "orchestrator_status": health.get("dependencies", {}).get("orchestrator", "unknown")
            }
    except Exception as e:
        return {
            "api_available": False,
            "error": str(e)
        }


async def check_market_hours() -> Dict[str, Any]:
    """Check if market is currently open."""
    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST)
    
    # Market hours: 9:15 AM - 3:30 PM IST, Monday-Friday
    is_weekday = now.weekday() < 5
    market_open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_open = market_open_time <= now < market_close_time
    
    return {
        "current_time_ist": now.isoformat(),
        "is_weekday": is_weekday,
        "market_open": is_open and is_weekday,
        "market_open_time": market_open_time.strftime("%H:%M"),
        "market_close_time": market_close_time.strftime("%H:%M"),
        "current_time": now.strftime("%H:%M:%S")
    }


async def check_technical_indicators() -> Dict[str, Any]:
    """Check latest technical indicators from Redis."""
    try:
        import redis
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        
        client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        
        # Get latest indicators for BANKNIFTY
        indicator_data = client.hgetall("indicators:BANKNIFTY:latest")
        
        if indicator_data:
            return {
                "available": True,
                "rsi_14": float(indicator_data.get("rsi_14", 0)),
                "macd_value": float(indicator_data.get("macd_value", 0)),
                "adx_14": float(indicator_data.get("adx_14", 0)),
                "current_price": float(indicator_data.get("current_price", 0)),
                "timestamp": indicator_data.get("timestamp", "unknown")
            }
        else:
            return {
                "available": False,
                "reason": "No indicator data found in Redis"
            }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }


async def analyze_market_conditions(indicators: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze if current market conditions are suitable for signals."""
    if not indicators.get("available"):
        return {
            "suitable": False,
            "reason": "Indicators not available"
        }
    
    rsi = indicators.get("rsi_14", 50)
    adx = indicators.get("adx_14", 0)
    
    # Check if conditions are suitable for each agent
    momentum_suitable = (rsi < 35 or rsi > 65)  # Oversold or overbought
    trend_suitable = (adx > 20)  # Strong trend
    
    analysis = {
        "rsi_value": rsi,
        "rsi_zone": "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral",
        "adx_value": adx,
        "trend_strength": "strong" if adx > 25 else "moderate" if adx > 15 else "weak",
        "momentum_agent_likely_signal": momentum_suitable,
        "trend_agent_likely_signal": trend_suitable,
        "overall_signal_probability": "HIGH" if (momentum_suitable and trend_suitable) else "MEDIUM" if (momentum_suitable or trend_suitable) else "LOW"
    }
    
    return analysis


async def trigger_manual_cycle() -> Dict[str, Any]:
    """Trigger a manual orchestrator cycle."""
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "http://localhost:8006/api/v1/analyze",
                json={
                    "instrument": "BANKNIFTY",
                    "context": {"market_hours": True}
                }
            )
            
            if resp.status_code == 200:
                result = resp.json()
                return {
                    "success": True,
                    "decision": result.get("decision"),
                    "confidence": result.get("confidence"),
                    "details": result.get("details", {})
                }
            else:
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "error": resp.text
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def clear_pending_signals() -> int:
    """Clear old pending signals from MongoDB."""
    try:
        from pymongo import MongoClient
        
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        
        client = MongoClient(mongo_uri)
        db = client[db_name]
        
        result = db['signals'].delete_many({
            "status": "pending",
            "is_active": True
        })
        
        return result.deleted_count
    except Exception as e:
        print_error(f"Failed to clear pending signals: {e}")
        return 0


async def main():
    """Run comprehensive diagnostic checks."""
    # Set UTF-8 encoding for Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    verbose = "--verbose" in sys.argv
    fix_pending = "--fix-pending" in sys.argv
    
    print_header("SIGNAL GENERATION SYSTEM DIAGNOSTIC")
    
    # 1. Check Redis
    print_header("1. Redis Connection & Data")
    redis_info = await check_redis_connection()
    if redis_info["connected"]:
        print_check("Redis Connection", True, f"{redis_info['host']}:{redis_info['port']}")
        print_check("Market Tick Keys", redis_info["tick_keys"] > 0, f"Found {redis_info['tick_keys']} keys")
        print_check("Indicator Keys", redis_info["indicator_keys"] > 0, f"Found {redis_info['indicator_keys']} keys")
    else:
        print_check("Redis Connection", False, redis_info.get("error", "Unknown error"))
    
    # 2. Check MongoDB
    print_header("2. MongoDB Connection & Signals")
    mongo_info = await check_mongodb_connection()
    if mongo_info["connected"]:
        print_check("MongoDB Connection", True, f"{mongo_info['database']}")
        print_info(f"Pending signals: {mongo_info['pending_signals']}")
        print_info(f"Triggered signals: {mongo_info['triggered_signals']}")
        print_info(f"Executed signals: {mongo_info['executed_signals']}")
        print_info(f"Expired signals: {mongo_info['expired_signals']}")
        
        if mongo_info["most_recent_signal"]:
            print_info(f"Most recent signal: {mongo_info['most_recent_action']} at {mongo_info['most_recent_signal']}")
        else:
            print_warning("No signals found in database")
        
        if fix_pending and mongo_info['pending_signals'] > 0:
            print_info(f"Clearing {mongo_info['pending_signals']} pending signals...")
            cleared = await clear_pending_signals()
            print_success(f"Cleared {cleared} pending signals")
    else:
        print_check("MongoDB Connection", False, mongo_info.get("error", "Unknown error"))
    
    # 3. Check Market Hours
    print_header("3. Market Hours Status")
    market_info = await check_market_hours()
    print_check("Market Open", market_info["market_open"], 
                f"Current time: {market_info['current_time']} IST")
    if not market_info["market_open"]:
        if not market_info["is_weekday"]:
            print_warning("Market closed: Weekend")
        else:
            print_warning(f"Market closed: Trading hours are {market_info['market_open_time']} - {market_info['market_close_time']} IST")
    
    # 4. Check Orchestrator API
    print_header("4. Engine API & Orchestrator")
    api_info = await check_orchestrator_api()
    if api_info["api_available"]:
        print_check("Engine API Available", True, "http://localhost:8006")
        orchestrator_status = api_info["orchestrator_status"]
        print_check("Orchestrator Initialized", 
                   orchestrator_status == "initialized",
                   f"Status: {orchestrator_status}")
    else:
        print_check("Engine API Available", False, api_info.get("error", "API not responding"))
        print_error("Engine API is not running! Start it with: python -m engine_module.api_service")
    
    # 5. Check Technical Indicators
    print_header("5. Technical Indicators")
    indicators = await check_technical_indicators()
    if indicators.get("available"):
        print_check("Indicators Available", True, f"Updated: {indicators.get('timestamp', 'unknown')}")
        print_info(f"Current Price: {indicators.get('current_price', 0):.2f}")
        print_info(f"RSI_14: {indicators.get('rsi_14', 0):.2f}")
        print_info(f"MACD: {indicators.get('macd_value', 0):.2f}")
        print_info(f"ADX_14: {indicators.get('adx_14', 0):.2f}")
        
        # Analyze market conditions
        analysis = await analyze_market_conditions(indicators)
        print_info(f"RSI Zone: {analysis.get('rsi_zone', 'unknown').upper()}")
        print_info(f"Trend Strength: {analysis.get('trend_strength', 'unknown').upper()}")
        print_info(f"Signal Probability: {analysis.get('overall_signal_probability', 'unknown')}")
        
        if analysis.get('overall_signal_probability') == "LOW":
            print_warning("Current market conditions unlikely to generate signals")
            print_warning("Agents likely returning HOLD decisions (neutral RSI, weak trend)")
    else:
        print_check("Indicators Available", False, indicators.get("reason", "Unknown error"))
    
    # 6. Trigger Manual Cycle (if API available and verbose mode)
    if api_info.get("api_available") and (verbose or "--manual-cycle" in sys.argv):
        print_header("6. Manual Orchestrator Cycle Test")
        print_info("Triggering manual cycle (this may take 10-30 seconds)...")
        
        cycle_result = await trigger_manual_cycle()
        if cycle_result.get("success"):
            print_check("Manual Cycle Executed", True)
            print_info(f"Decision: {cycle_result.get('decision', 'unknown')}")
            print_info(f"Confidence: {cycle_result.get('confidence', 0):.2f}")
            
            if verbose and cycle_result.get('details'):
                print_info("\nAgent Breakdown:")
                agent_signals = cycle_result['details'].get('agent_signals', {})
                for agent_name, signal in agent_signals.items():
                    print(f"   {agent_name}: {signal.get('decision')} (conf: {signal.get('confidence', 0):.2f})")
        else:
            print_check("Manual Cycle Executed", False, cycle_result.get("error", "Unknown error"))
    
    # 7. Summary and Recommendations
    print_header("DIAGNOSIS SUMMARY")
    
    all_systems_go = (
        redis_info.get("connected") and
        mongo_info.get("connected") and
        api_info.get("api_available")
    )
    
    if all_systems_go:
        print_success("All core systems are operational")
        
        if indicators.get("available"):
            analysis = await analyze_market_conditions(indicators)
            if analysis.get('overall_signal_probability') == "LOW":
                print_warning("\nLOW SIGNAL PROBABILITY - Neutral Market Conditions")
                print_info("Reason: Current market indicators do not meet agent signal criteria")
                print_info(f"- RSI {indicators.get('rsi_14', 0):.2f} (neutral, not oversold/overbought)")
                print_info(f"- ADX {indicators.get('adx_14', 0):.2f} (weak trend, below 20 threshold)")
                print_info("\nRecommendation:")
                print_info("   System is working correctly - wait for stronger market conditions:")
                print_info("   • RSI < 35 or > 65 (momentum signals)")
                print_info("   • ADX > 20 (trend signals)")
                print_info("   • Volume spikes (confirmation)")
            elif analysis.get('overall_signal_probability') == "MEDIUM":
                print_warning("\nMEDIUM SIGNAL PROBABILITY")
                print_info("Some conditions met, but not all agents may agree")
            else:
                print_success("\nHIGH SIGNAL PROBABILITY - Good conditions for signals")
        
        if mongo_info.get("pending_signals", 0) > 0:
            print_info(f"\n{mongo_info['pending_signals']} pending signals in database")
            print_info("   Use --fix-pending flag to clear old pending signals")
        
        if not market_info.get("market_open"):
            print_warning("\nMarket is currently CLOSED")
            print_info("   Orchestrator cycles will resume when market opens")
    else:
        print_error("\nCRITICAL ISSUES DETECTED:")
        
        if not redis_info.get("connected"):
            print_error("   - Redis not connected - Start Redis server")
        
        if not mongo_info.get("connected"):
            print_error("   - MongoDB not connected - Start MongoDB server")
        
        if not api_info.get("api_available"):
            print_error("   - Engine API not running - Start engine service:")
            print_info("     python -m engine_module.api_service")
    
    print_header("QUICK FIX COMMANDS")
    print(f"{BLUE}# Start all services:{RESET}")
    print("python start_local.py")
    print(f"\n{BLUE}# Clear pending signals:{RESET}")
    print("python scripts/diagnose_signals.py --fix-pending")
    print(f"\n{BLUE}# Force manual cycle with verbose output:{RESET}")
    print("python scripts/diagnose_signals.py --verbose --manual-cycle")
    print(f"\n{BLUE}# Monitor logs in real-time:{RESET}")
    print("tail -f logs/engine.log | grep -i 'cycle\\|signal'")
    
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
