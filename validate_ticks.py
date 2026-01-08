"""Validate ticks - compare live vs historical prices and timestamps"""
import redis
import json
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

def get_redis_data():
    """Get current data from Redis"""
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    # Get latest tick
    tick_key = "tick:BANKNIFTY:latest"
    tick_data = r.get(tick_key)
    
    # Get latest price
    price_key = "price:BANKNIFTY:latest"
    price = r.get(price_key)
    
    # Get latest timestamp
    ts_key = "price:BANKNIFTY:latest_ts"
    timestamp = r.get(ts_key)
    
    # Get virtual time (if historical mode)
    virtual_time_enabled = r.get("system:virtual_time:enabled")
    virtual_time_current = r.get("system:virtual_time:current")
    
    # Get some recent ticks
    tick_keys = r.keys("tick:BANKNIFTY:*")
    recent_ticks = []
    if tick_keys:
        # Get a few recent ones (not all, just sample)
        for key in sorted(tick_keys)[-5:]:
            tick = r.get(key)
            if tick:
                try:
                    tick_obj = json.loads(tick)
                    recent_ticks.append({
                        'key': key,
                        'price': tick_obj.get('last_price'),
                        'timestamp': tick_obj.get('timestamp'),
                        'volume': tick_obj.get('volume')
                    })
                except:
                    pass
    
    return {
        'latest_tick': json.loads(tick_data) if tick_data else None,
        'latest_price': float(price) if price else None,
        'latest_timestamp': timestamp,
        'virtual_time_enabled': virtual_time_enabled == "1" if virtual_time_enabled else False,
        'virtual_time_current': virtual_time_current,
        'recent_ticks': recent_ticks,
        'total_tick_keys': len(tick_keys) if tick_keys else 0
    }

def analyze_data(data):
    """Analyze and display the data"""
    print("=" * 70)
    print("TICK VALIDATION - Live vs Historical Comparison")
    print("=" * 70)
    
    if not data['latest_tick']:
        print("ERROR: No tick data found in Redis")
        return
    
    # Latest tick info
    latest_tick = data['latest_tick']
    latest_price = data['latest_price']
    latest_ts_str = data['latest_timestamp']
    
    print(f"\nCurrent Data in Redis:")
    print(f"   Latest Price: {latest_price}")
    print(f"   Latest Timestamp: {latest_ts_str}")
    print(f"   Total Tick Keys: {data['total_tick_keys']}")
    
    # Parse timestamp (assume IST if no timezone)
    if latest_ts_str:
        try:
            latest_ts = parse(latest_ts_str)
            # If no timezone, assume IST (Indian Standard Time)
            if latest_ts.tzinfo is None:
                latest_ts = latest_ts.replace(tzinfo=IST)
                print(f"\nTimestamp Analysis (assuming IST):")
            else:
                print(f"\nTimestamp Analysis:")
            
            # Current time in IST
            now_ist = datetime.now(IST)
            age_seconds = (now_ist - latest_ts).total_seconds()
            age_hours = age_seconds / 3600
            age_days = age_seconds / 86400
            
            print(f"   Data Timestamp: {latest_ts.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"   Current Time (IST): {now_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"   Age: {age_days:.1f} days ({age_hours:.1f} hours, {age_seconds:.0f} seconds)")
            
            # Check if market is open (9:15 AM - 3:30 PM IST, Mon-Fri)
            market_open = False
            if latest_ts.weekday() < 5:  # Monday-Friday
                hour = latest_ts.hour
                minute = latest_ts.minute
                if (hour == 9 and minute >= 15) or (9 < hour < 15) or (hour == 15 and minute <= 30):
                    market_open = True
            
            if age_days > 1:
                print(f"\nMODE: HISTORICAL")
                print(f"   This is historical data from {latest_ts.strftime('%Y-%m-%d')}")
                print(f"   Historical Price on {latest_ts.strftime('%Y-%m-%d %H:%M:%S IST')}: {latest_price}")
            elif age_seconds < 300:  # Less than 5 minutes
                print(f"\nMODE: LIVE")
                print(f"   This is live/current data")
                print(f"   Current Live Price: {latest_price}")
                print(f"   Market was open: {market_open}")
            else:
                # Check if this is from today during market hours
                today = now_ist.date()
                data_date = latest_ts.date()
                if data_date == today and market_open:
                    print(f"\nMODE: LIVE (from earlier today during market hours)")
                    print(f"   Price: {latest_price}")
                    print(f"   Time: {latest_ts.strftime('%H:%M:%S IST')}")
                    print(f"   Age: {age_hours:.1f} hours (market may be closed now)")
                else:
                    print(f"\nMODE: STALE or HISTORICAL")
                    print(f"   Data is {age_hours:.1f} hours old")
                    print(f"   Price: {latest_price}")
                    print(f"   Date: {data_date} (Today: {today})")
        except Exception as e:
            print(f"   ERROR parsing timestamp: {e}")
    
    # Virtual time check
    print(f"\nVirtual Time Status:")
    if data['virtual_time_enabled']:
        print(f"   Virtual Time: ENABLED (Historical Replay Mode)")
        if data['virtual_time_current']:
            try:
                vt = parse(data['virtual_time_current'])
                print(f"   Virtual Time: {vt.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            except:
                print(f"   Virtual Time: {data['virtual_time_current']}")
    else:
        print(f"   Virtual Time: DISABLED (Live Mode)")
    
    # Recent ticks sample
    if data['recent_ticks']:
        print(f"\nRecent Ticks Sample (last 5):")
        for i, tick in enumerate(data['recent_ticks'], 1):
            ts = tick.get('timestamp', 'N/A')
            price = tick.get('price', 'N/A')
            vol = tick.get('volume', 'N/A')
            print(f"   {i}. Price: {price}, Time: {ts}, Volume: {vol}")
    
    # Validation summary
    print(f"\nVALIDATION SUMMARY:")
    if latest_ts_str:
        try:
            latest_ts = parse(latest_ts_str)
            # Assume IST if no timezone
            if latest_ts.tzinfo is None:
                latest_ts = latest_ts.replace(tzinfo=IST)
            
            now_ist = datetime.now(IST)
            age_seconds = (now_ist - latest_ts).total_seconds()
            age_days = age_seconds / 86400
            age_hours = age_seconds / 3600
            
            today = now_ist.date()
            data_date = latest_ts.date()
            
            if age_days > 1:
                print(f"   OK: Historical data confirmed")
                print(f"   Date: {latest_ts.strftime('%Y-%m-%d')}")
                print(f"   Historical Price: {latest_price}")
                print(f"   Age: {age_days:.1f} days old")
            elif age_seconds < 300:  # Less than 5 minutes
                print(f"   OK: Live data confirmed")
                print(f"   Current Price: {latest_price}")
                print(f"   Timestamp: {latest_ts.strftime('%Y-%m-%d %H:%M:%S IST')}")
            elif data_date == today:
                print(f"   OK: Live data from today (market may be closed now)")
                print(f"   Price: {latest_price}")
                print(f"   Time: {latest_ts.strftime('%H:%M:%S IST')}")
                print(f"   Age: {age_hours:.1f} hours")
            else:
                print(f"   WARNING: Stale data (not clearly live or historical)")
                print(f"   Price: {latest_price}")
                print(f"   Date: {data_date} (Today: {today})")
                print(f"   Age: {age_hours:.1f} hours")
        except Exception as e:
                print(f"   WARNING: Could not determine mode from timestamp: {e}")

def get_current_live_price():
    """Try to get current live price from Zerodha API"""
    try:
        import sys
        import os
        sys.path.insert(0, '.')
        from providers.factory import get_provider
        
        provider = get_provider()
        if provider:
            # Get quote for NIFTY BANK (Zerodha format)
            quote = provider.quote(["NSE:NIFTY BANK"])
            if quote:
                q = list(quote.values())[0]
                if hasattr(q, 'last_price'):
                    return q.last_price
                elif isinstance(q, dict):
                    return q.get('last_price')
        return None
    except Exception as e:
        return None

def main():
    try:
        data = get_redis_data()
        analyze_data(data)
        
        # Try to get current live price for comparison
        print(f"\n" + "=" * 70)
        print("LIVE PRICE COMPARISON")
        print("=" * 70)
        
        current_live = get_current_live_price()
        if current_live:
            print(f"\nCurrent Live Price (from Zerodha API): {current_live}")
            if data['latest_price']:
                diff = current_live - data['latest_price']
                diff_pct = (diff / data['latest_price']) * 100 if data['latest_price'] else 0
                print(f"Redis Price: {data['latest_price']}")
                print(f"Difference: {diff:+.2f} ({diff_pct:+.2f}%)")
                
                if abs(diff_pct) < 0.1:
                    print("OK: Prices match - data is current!")
                elif abs(diff_pct) < 1.0:
                    print("WARNING: Small difference - data may be slightly stale")
                else:
                    print("WARNING: Significant difference - data is stale or historical")
        else:
            print("\nCould not fetch current live price (credentials may be needed)")
            print("To validate:")
            print("  1. Check if market is open (9:15 AM - 3:30 PM IST)")
            print("  2. Verify Zerodha credentials are configured")
            print("  3. Historical data timestamp shows the date it's from")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

