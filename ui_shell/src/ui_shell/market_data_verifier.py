"""Market Data API Verifier - Simple tool to check market_data APIs."""

import asyncio
import json
import httpx
from typing import Dict, Any
from datetime import datetime


class MarketDataVerifier:
    """Simple verifier for market_data APIs."""

    def __init__(self, base_url: str = "http://127.0.0.1:8006"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=5.0)

    async def verify_all_apis(self) -> Dict[str, Any]:
        """Verify all market data APIs."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "apis": {}
        }

        # Test Health
        print("Testing Health API...")
        health = await self._test_health()
        results["apis"]["health"] = health
        print(f"  Status: {'PASS' if health.get('status') == 'healthy' else 'FAIL'}")

        # Test Price Data
        print("Testing Price API...")
        price = await self._test_price("BANKNIFTY")
        results["apis"]["price"] = price
        print(f"  Status: {'PASS' if price.get('success') else 'FAIL'}")

        # Test Options Chain
        print("Testing Options Chain API...")
        options = await self._test_options("BANKNIFTY")
        results["apis"]["options"] = options
        print(f"  Status: {'PASS' if options.get('success') else 'FAIL'}")

        # Test Technical Indicators
        print("Testing Technical Indicators API...")
        indicators = await self._test_indicators("BANKNIFTY")
        results["apis"]["indicators"] = indicators
        print(f"  Status: {'PASS' if indicators.get('success') else 'FAIL'}")

        # Summary
        working = sum(1 for api in results["apis"].values() if api.get("success"))
        total = len(results["apis"])
        results["summary"] = f"{working}/{total} APIs working"

        print(f"\nSUMMARY: {working}/{total} APIs working")

        return results

    async def _test_health(self) -> Dict[str, Any]:
        """Test health endpoint."""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()
            return {
                "success": data.get("status") == "healthy",
                "status": data.get("status"),
                "data": data
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_price(self, instrument: str) -> Dict[str, Any]:
        """Test price endpoint."""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/market/price/{instrument}")
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "instrument": data.get("instrument"),
                "has_price": data.get("price") is not None,
                "is_stale": data.get("is_stale", False),
                "data": data
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_options(self, instrument: str) -> Dict[str, Any]:
        """Test options chain endpoint."""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/options/chain/{instrument}")
            response.raise_for_status()
            data = response.json()
            strikes = data.get("strikes", [])
            return {
                "success": True,
                "instrument": data.get("instrument"),
                "strikes_count": len(strikes),
                "expiry": data.get("expiry"),
                "sample_strikes": strikes[:3] if strikes else []
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_indicators(self, instrument: str) -> Dict[str, Any]:
        """Test technical indicators endpoint."""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/technical/indicators/{instrument}")
            if response.status_code == 404:
                # Expected when no indicators cached
                return {
                    "success": True,
                    "message": "No indicators available (expected for external calculation)",
                    "status_code": 404
                }
            response.raise_for_status()
            data = response.json()
            indicators = data.get("indicators", {})
            return {
                "success": True,
                "instrument": data.get("instrument"),
                "indicators_count": len(indicators),
                "sample_indicators": list(indicators.keys())[:5]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def show_raw_data(self, instrument: str = "BANKNIFTY"):
        """Show raw data from all APIs."""
        print(f"RAW DATA FOR {instrument}")
        print("=" * 50)

        # Price Data
        print("\nPRICE DATA:")
        price = await self._test_price(instrument)
        if price["success"]:
            data = price["data"]
            print(json.dumps(data, indent=2))
        else:
            print(f"Error: {price.get('error')}")

        # Options Chain (first 2 strikes)
        print("\nOPTIONS CHAIN (first 2 strikes):")
        options = await self._test_options(instrument)
        if options["success"]:
            strikes = options.get("sample_strikes", [])
            print(json.dumps({
                "instrument": options["instrument"],
                "expiry": options["expiry"],
                "strikes": strikes
            }, indent=2))
        else:
            print(f"Error: {options.get('error')}")

        # Technical Indicators
        print("\nTECHNICAL INDICATORS:")
        indicators = await self._test_indicators(instrument)
        if indicators["success"]:
            if "message" in indicators:
                print(indicators["message"])
            else:
                print(json.dumps({
                    "instrument": indicators["instrument"],
                    "indicators_count": indicators["indicators_count"],
                    "available_indicators": indicators["sample_indicators"]
                }, indent=2))
        else:
            print(f"Error: {indicators.get('error')}")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


async def main():
    """Main verifier function."""
    import sys

    verifier = MarketDataVerifier()

    try:
        if len(sys.argv) > 1 and sys.argv[1] == "raw":
            # Show raw data
            instrument = sys.argv[2] if len(sys.argv) > 2 else "BANKNIFTY"
            await verifier.show_raw_data(instrument)
        else:
            # Verify all APIs
            results = await verifier.verify_all_apis()

            # Save results
            with open("market_data_verification.json", "w") as f:
                json.dump(results, f, indent=2)

            print(f"\n💾 Results saved to market_data_verification.json")

    finally:
        await verifier.close()


if __name__ == "__main__":
    asyncio.run(main())
