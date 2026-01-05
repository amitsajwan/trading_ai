#!/usr/bin/env python3
"""Setup paper trading account with 5 lakh capital."""

import asyncio
import sys
import os

# Add module paths
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'user_module', 'src'))

from user_module.api import build_user_module, create_user_account
from pymongo import MongoClient
from user_module.contracts import RiskProfile

async def setup_paper_trading_account():
    """Create a paper trading account with 5 lakh capital."""

    # Connect to MongoDB
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/zerodha_trading")
    mongo_client = MongoClient(mongo_uri)

    try:
        # Build user module
        user_service = build_user_module(mongo_client)

        # Create conservative risk profile for paper trading
        from user_module.services import RiskProfileManager
        risk_mgr = RiskProfileManager(None)
        risk_profile = risk_mgr.get_risk_profile("conservative")  # Use predefined profile

        # Create user account with 5 lakh capital
        user_id = await create_user_account(
            mongo_client=mongo_client,
            email="paper_trader@example.com",
            full_name="Paper Trading Account",
            risk_profile="conservative"
        )

        print("Paper Trading Account Created!")
        print(f"User ID: {user.user_id}")
        print(f"Email: {user.email}")
        print(f"Initial Capital: Rs.{user.balances.get('INR', 0):,.0f}")
        print(f"Risk Profile: Conservative")
        print(f"Max Daily Loss: Rs.25,000")
        print(f"Max Position Size: Rs.1,00,000")

        return user.user_id

    except Exception as e:
        print(f"Error setting up paper trading account: {e}")
        return None

if __name__ == "__main__":
    user_id = asyncio.run(setup_paper_trading_account())
    if user_id:
        print(f"\nReady to start paper trading with user ID: {user_id}")
        print("Use this ID with the trading APIs to execute paper trades.")
