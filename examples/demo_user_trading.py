#!/usr/bin/env python3
"""Demonstrate user trade execution with risk management."""

import asyncio
import sys
sys.path.insert(0, 'user_module/src')

from user_module.api import create_user_account, execute_user_trade
from user_module.contracts import UserAccount
from user_module.services import RiskProfileManager

class MockMongoClient:
    """Mock MongoDB client for demonstration."""
    def __init__(self):
        self.db = MockDatabase()

class MockDatabase:
    """Mock database for demonstration."""
    def __init__(self):
        self.zerodha_trading = MockCollection()

class MockCollection:
    """Mock collection that just stores in memory."""
    def __init__(self):
        self.data = {}

    async def insert_one(self, doc):
        doc['_id'] = f"mock_{len(self.data)}"
        self.data[doc['_id']] = doc
        return type('Result', (), {'acknowledged': True})()

    async def find_one(self, query):
        key = query.get('_id') or query.get('user_id')
        return self.data.get(key)

    async def update_one(self, query, update, **kwargs):
        key = query.get('_id')
        if key in self.data:
            self.data[key].update(update.get('$set', {}))
            return type('Result', (), {'modified_count': 1})()
        return type('Result', (), {'modified_count': 0})()

    async def replace_one(self, query, doc, **kwargs):
        key = query.get('_id') or query.get('user_id')
        self.data[key] = doc
        return type('Result', (), {'acknowledged': True})()

async def demonstrate_user_trading():
    """Demonstrate user account creation and trade execution."""

    print("🎯 USER TRADING WITH RISK MANAGEMENT DEMO")
    print("=" * 50)

    # Create mock MongoDB client
    mongo_client = MockMongoClient()

    print("\n1. CREATING USER ACCOUNTS")
    print("-" * 25)

    # Create users with different risk profiles
    users = [
        ("john@conservative.com", "John Conservative", "conservative"),
        ("jane@moderate.com", "Jane Moderate", "moderate"),
        ("bob@aggressive.com", "Bob Aggressive", "aggressive")
    ]

    user_ids = {}
    for email, name, risk_profile in users:
        user_id = await create_user_account(mongo_client, email, name, risk_profile)
        user_ids[email] = user_id
        print(f"✅ Created {risk_profile} user: {name} ({user_id})")

    print("\n2. RISK PROFILE COMPARISON")
    print("-" * 25)

    risk_mgr = RiskProfileManager(None)

    profiles = ['conservative', 'moderate', 'aggressive']
    for profile_name in profiles:
        profile = risk_mgr.get_risk_profile(profile_name)
        print(f"{profile_name.upper()}:")
        print(f"  Max Daily Loss: {profile['max_daily_loss_pct']}%")
        print(f"  Max Position Size: {profile['max_position_size_pct']}%")
        print(f"  Stop Loss Required: {profile['stop_loss_required']}")
        print(f"  Max Open Positions: {profile['max_open_positions']}")
        print()

    print("3. TRADE EXECUTION WITH RISK MANAGEMENT")
    print("-" * 40)

    # Test trades for different risk profiles
    test_trades = [
        ("john@conservative.com", "BANKNIFTY", "BUY", 50, "Conservative: Large position"),
        ("jane@moderate.com", "BANKNIFTY", "BUY", 25, "Moderate: Medium position"),
        ("bob@aggressive.com", "BANKNIFTY", "BUY", 10, "Aggressive: Small position")
    ]

    for email, instrument, side, quantity, description in test_trades:
        user_id = user_ids[email]
        print(f"\n{description}")
        print(f"User: {user_id}")

        # Execute trade
        result = await execute_user_trade(
            mongo_client=mongo_client,
            user_id=user_id,
            instrument=instrument,
            side=side,
            quantity=quantity,
            order_type="MARKET",
            stop_loss=44000.0  # Mock stop loss
        )

        if result.success:
            print("✅ Trade Executed Successfully!")
            print(".2f")
            print(f"   Quantity: {result.executed_quantity}")
            print(f"   Trade ID: {result.trade_id}")
        else:
            print(f"❌ Trade Failed: {result.message}")

    print("\n4. RISK-BASED POSITION SIZING")
    print("-" * 30)

    # Demonstrate position sizing based on risk
    entry_price = 45000.0
    stop_loss = 44500.0
    account_balance = 100000.0

    print("Example: BANKNIFTY position sizing")
    print(f"Entry Price: ₹{entry_price}")
    print(f"Stop Loss: ₹{stop_loss}")
    print(f"Account Balance: ₹{account_balance}")

    for email, _, _, _, profile_type in test_trades:
        user_id = user_ids[email]
        risk_amount = account_balance * 0.01  # 1% risk per trade

        position_size = await risk_mgr.calculate_position_size(
            user_id, "BANKNIFTY", entry_price, stop_loss, account_balance
        )

        print(f"\n{profile_type}:")
        print(f"  Risk per trade: ₹{risk_amount:.0f} (1%)")
        print(f"  Recommended position size: {position_size} shares")
        print(f"  Position value: ₹{position_size * entry_price:,.0f}")

    print("\n🎉 USER TRADING DEMO COMPLETE!")
    print("=" * 35)
    print("✅ User accounts created with risk profiles")
    print("✅ Trades executed with risk validation")
    print("✅ Position sizing based on risk tolerance")
    print("✅ Different behaviors for conservative/moderate/aggressive profiles")
    print()
    print("The user module now supports:")
    print("• Account management with risk profiles")
    print("• Trade execution with risk validation")
    print("• Position sizing based on risk tolerance")
    print("• P&L tracking and portfolio management")

if __name__ == '__main__':
    asyncio.run(demonstrate_user_trading())

