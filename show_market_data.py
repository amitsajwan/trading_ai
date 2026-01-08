#!/usr/bin/env python3
"""Display Market Data APIs - Simple Console Dashboard."""

import asyncio
import json
import httpx
from datetime import datetime


class MarketDataDisplay:
    """Simple display for market data APIs."""

    def __init__(self, base_url: str = "http://127.0.0.1:8006"):
        self.base_url = base_url.rstrip('/')

    async def display_all_data(self):
        """Display all market data in a trader-friendly format."""
        print("BANKNIFTY MARKET DATA DASHBOARD")
        print("=" * 60)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Get all data in parallel
                price_resp = await client.get(f"{self.base_url}/api/v1/market/price/BANKNIFTY")
                options_resp = await client.get(f"{self.base_url}/api/v1/options/chain/BANKNIFTY")
                indicators_resp = await client.get(f"{self.base_url}/api/v1/technical/indicators/BANKNIFTY")
                health_resp = await client.get(f"{self.base_url}/health")

                # Process responses
                price_data = price_resp.json() if price_resp.status_code == 200 else None
                options_data = options_resp.json() if options_resp.status_code == 200 else None
                indicators_data = indicators_resp.json() if indicators_resp.status_code == 200 else None
                health_data = health_resp.json() if health_resp.status_code == 200 else None

                # Display system health
                if health_data:
                    status = "HEALTHY" if health_data.get("status") == "healthy" else "ISSUES"
                    print(f"System Status: {status}")
                else:
                    print("System Status: UNAVAILABLE")
                print()

                # Display price data
                print("PRICE DATA")
                print("-" * 30)
                if price_data and price_data.get("price"):
                    price = price_data["price"]
                    volume = price_data.get("volume", "N/A")
                    is_stale = price_data.get("is_stale", False)
                    timestamp = price_data.get("timestamp", "N/A")

                    status_icon = "[STALE]" if is_stale else "[LIVE]"
                    print(f"Current Price: {status_icon} Rs.{price:,.0f}")
                    print(f"Volume: {volume if volume != 'N/A' else 'N/A'}")
                    print(f"Last Update: {timestamp[:19] if timestamp != 'N/A' else 'N/A'}")
                    print(f"Data Status: {'After Hours' if is_stale else 'Live'}")
                else:
                    print("ERROR: No price data available")
                print()

                # Display technical indicators
                print("TECHNICAL INDICATORS")
                print("-" * 30)
                if indicators_data and indicators_data.get("indicators"):
                    indicators = indicators_data["indicators"]
                    trend = indicators.get("trend", {})

                    # Key indicators
                    rsi = trend.get("rsi_14")
                    macd = trend.get("macd_value")
                    bb_upper = indicators.get("volatility", {}).get("bollinger_upper")
                    sma = trend.get("sma_20")

                    if rsi:
                        print(f"RSI (14): {rsi:.1f}")
                    if macd:
                        print(f"MACD: {macd:.2f}")
                    if bb_upper:
                        print(f"Bollinger Upper: {bb_upper:.0f}")
                    if sma:
                        print(f"SMA (20): {sma:.0f}")

                    # Available indicators count
                    total_indicators = len(indicators)
                    print(f"Total Indicators Available: {total_indicators}")

                else:
                    print("ERROR: No technical indicators available")
                print()

                # Display options chain summary
                print("OPTIONS CHAIN")
                print("-" * 30)
                if options_data and options_data.get("strikes"):
                    strikes = options_data["strikes"]
                    expiry = options_data.get("expiry", "Unknown")

                    print(f"Expiry Date: {expiry}")
                    print(f"Total Strikes: {len(strikes)}")

                    # Show first few strikes
                    print("\nFirst 5 Strikes:")
                    print("Strike   | Call Price | Put Price")
                    print("-" * 35)

                    for i, strike_data in enumerate(strikes[:5]):
                        strike = strike_data.get("strike", 0)
                        call = strike_data.get("call", {})
                        put = strike_data.get("put", {})

                        call_price = call.get("last_price", "-") if call else "-"
                        put_price = put.get("last_price", "-") if put else "-"

                        print(f"{strike:6.0f}   | {call_price:>10} | {put_price:>9}")
                else:
                    print("ERROR: No options chain data available")
                print()

                # Summary
                print("📊 SUMMARY")
                print("-" * 30)
                apis_working = sum([
                    1 if price_data and price_data.get("price") else 0,
                    1 if options_data and options_data.get("strikes") else 0,
                    1 if indicators_data and indicators_data.get("indicators") else 0,
                    1 if health_data and health_data.get("status") == "healthy" else 0
                ])

                print(f"APIs Working: {apis_working}/4")
                print(f"Data Source: market_data module (port 8006)")
                print(f"Last Refresh: {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            print(f"ERROR: Error connecting to market data service: {e}")
            print("Make sure the market_data server is running on port 8006")
            print("Run: python start_market_data_server.py")


async def main():
    """Main display function."""
    display = MarketDataDisplay()

    print("Loading market data...")
    print()

    await display.display_all_data()

    print("\n" + "=" * 60)
    print("INFO: This data comes from the market_data module APIs:")
    print("   - Real Zerodha historical data (2250 candles)")
    print("   - pandas-ta technical indicators")
    print("   - 138 BANKNIFTY options strikes")
    print("   - After-hours compatible (cached prices)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
