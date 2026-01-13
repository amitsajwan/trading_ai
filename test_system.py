#!/usr/bin/env python3
"""
Test script to monitor and trace the trading system operations.
"""

import requests
import json
import time
from datetime import datetime

def test_api_health():
    """Test all API health endpoints."""
    print("=" * 60)
    print("🔍 API HEALTH CHECK")
    print("=" * 60)

    apis = [
        ('Market Data', 'http://localhost:8004/health'),
        ('Engine', 'http://localhost:8006/health'),
        ('News', 'http://localhost:8005/health'),
        ('User', 'http://localhost:8007/health'),
    ]

    for name, url in apis:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {name} API: HEALTHY ({response.elapsed.total_seconds():.2f}s)")
                # Show key details
                if 'dependencies' in data:
                    deps = data['dependencies']
                    print(f"   Dependencies: {', '.join([f'{k}:{v}' for k,v in deps.items()])}")
            else:
                print(f"❌ {name} API: ERROR {response.status_code}")
        except Exception as e:
            print(f"❌ {name} API: FAILED - {e}")

def test_market_data():
    """Test market data retrieval."""
    print("\n" + "=" * 60)
    print("📊 MARKET DATA TEST")
    print("=" * 60)

    try:
        # Get current tick
        response = requests.get('http://localhost:8004/api/v1/market/tick/BANKNIFTY')
        if response.status_code == 200:
            data = response.json()
            print("✅ Current Tick Data:")
            print(f"   Instrument: {data['instrument']}")
            print(f"   Price: ₹{data['last_price']:.2f}")
            print(f"   Timestamp: {data['timestamp']}")
            print(f"   Volume: {data['volume']}")
        else:
            print(f"❌ Tick data failed: {response.status_code}")

        # Get OHLC data
        response = requests.get('http://localhost:8004/api/v1/market/ohlc/BANKNIFTY?timeframe=minute&limit=3')
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Recent OHLC Data (last 3 bars):")
            for bar in data[-3:]:
                print(f"   {bar['start_at']}: O:{bar['open']:.1f} H:{bar['high']:.1f} L:{bar['low']:.1f} C:{bar['close']:.1f} V:{bar['volume']}")
        else:
            print(f"❌ OHLC data failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Market data test failed: {e}")

def test_engine_analysis():
    """Test engine analysis capabilities."""
    print("\n" + "=" * 60)
    print("🤖 ENGINE ANALYSIS TEST")
    print("=" * 60)

    try:
        print("⏳ Running comprehensive analysis...")
        start_time = time.time()

        response = requests.post(
            'http://localhost:8006/api/v1/analyze',
            json={'instrument': 'BANKNIFTY'},
            timeout=120  # 2 minute timeout for analysis
        )

        analysis_time = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            print(".2f")
            print(f"   Decision: {data['decision']} (Confidence: {data['confidence']:.1%})")

            details = data['details']
            print(f"   Market Hours: {details['market_hours']}")
            print(f"   Agents Run: {details['agents_run']}")
            print(f"   Analysis Duration: {details['analysis_duration_seconds']:.1f}s")

            # Show agent breakdown
            agg = details['aggregated_analysis']
            breakdown = agg['agent_breakdown']
            print(f"   Agent Signals: BUY:{breakdown['buy_signals']} SELL:{breakdown['sell_signals']} HOLD:{breakdown['hold_signals']}")

            # Show top insights
            if 'key_insights' in agg:
                print("\n   Key Insights:")
                for insight in agg['key_insights'][:3]:
                    print(f"   • {insight}")

        else:
            print(f"❌ Analysis failed: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Engine analysis test failed: {e}")

def test_signal_monitoring():
    """Test signal monitoring system."""
    print("\n" + "=" * 60)
    print("🎯 SIGNAL MONITORING TEST")
    print("=" * 60)

    try:
        response = requests.get('http://localhost:8006/api/v1/signals/BANKNIFTY')
        if response.status_code == 200:
            signals = response.json()
            print(f"✅ Found {len(signals)} active signals:")

            for i, signal in enumerate(signals, 1):
                print(f"\n   Signal {i}:")
                print(f"   ID: {signal['signal_id']}")
                print(f"   Action: {signal['action']}")
                print(f"   Confidence: {signal['confidence']:.1%}")
                print(f"   Entry Price: ₹{signal['entry_price']:.2f}")
                print(f"   Status: {signal['status']}")
                print(f"   Threshold: {signal['threshold']:.2f}")

        else:
            print(f"❌ Signal check failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Signal monitoring test failed: {e}")

def test_performance_monitoring():
    """Test performance monitoring system."""
    print("\n" + "=" * 60)
    print("📈 PERFORMANCE MONITORING TEST")
    print("=" * 60)

    try:
        from monitoring import get_performance_monitor, get_metrics_collector

        perf_monitor = get_performance_monitor()
        metrics = get_metrics_collector()

        # Get performance summary
        summary = perf_monitor.get_metrics_summary()

        print("✅ System Performance Summary:")
        print(f"   Uptime: {summary['uptime_seconds']:.0f} seconds ({summary['uptime_seconds']/3600:.1f} hours)")

        if summary['function_metrics']:
            print(f"   Functions Monitored: {len(summary['function_metrics'])}")
            for name, data in list(summary['function_metrics'].items())[:3]:
                print(f"   • {name}: {data['calls']} calls, {data['avg_duration']:.3f}s avg")

        if summary['system_metrics']:
            print("   System Resources:")
            for name, data in summary['system_metrics'].items():
                if 'cpu' in name.lower():
                    print(f"   • CPU Usage: {data['current']:.1f}% (avg: {data['avg']:.1f}%)")

        # Get metrics stats
        tick_metrics = metrics.get_metric_stats("price_gauge", hours=0.1)
        if tick_metrics:
            print(f"\n   Recent Metrics: {tick_metrics['count']} price updates in last 6 minutes")
            print(f"   Price Range: ₹{tick_metrics['min_value']:.2f} - ₹{tick_metrics['max_value']:.2f}")

    except Exception as e:
        print(f"❌ Performance monitoring test failed: {e}")

def monitor_real_time():
    """Monitor real-time data feed."""
    print("\n" + "=" * 60)
    print("🔄 REAL-TIME MONITORING")
    print("=" * 60)

    print("Monitoring real-time data feed for 30 seconds...")
    print("(Press Ctrl+C to stop)")

    try:
        start_time = time.time()
        last_price = None

        while time.time() - start_time < 30:
            try:
                response = requests.get('http://localhost:8004/api/v1/market/tick/BANKNIFTY', timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    current_price = data['last_price']

                    if current_price != last_price:
                        timestamp = datetime.fromisoformat(data['timestamp'].replace('+05:30', ''))
                        print(f"📈 {timestamp.strftime('%H:%M:%S')}: ₹{current_price:.2f} (Vol: {data['volume']})")
                        last_price = current_price

                time.sleep(2)  # Update every 2 seconds

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️  Connection error: {e}")
                time.sleep(1)

    except KeyboardInterrupt:
        pass

    print("\n✅ Real-time monitoring completed")

def main():
    """Run all system tests."""
    print(f"🧪 TRADING SYSTEM COMPREHENSIVE TEST")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Run all tests
    test_api_health()
    test_market_data()
    test_engine_analysis()
    test_signal_monitoring()
    test_performance_monitoring()

    # Real-time monitoring (commented out to avoid hanging)
    # monitor_real_time()

    print("\n" + "=" * 80)
    print("🎉 SYSTEM TEST COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    main()