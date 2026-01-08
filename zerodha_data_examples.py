"""
Example data structures for Zerodha API responses.
Use these as templates when simulating historical data.
"""

from datetime import datetime, date, timezone, timedelta
from typing import Dict, List, Optional, Any

# ============================================================================
# 1. MARKET TICK DATA
# ============================================================================

def example_ltp_response() -> Dict[str, Any]:
    """Example response from kite.ltp()"""
    return {
        "NSE:NIFTY BANK": {
            "last_price": 45050.0,
            "volume": 1500000,
            "ohlc": {
                "open": 45000.0,
                "high": 45100.0,
                "low": 44950.0,
                "close": 45050.0
            },
            "net_change": 50.0,
            "timestamp": datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
        }
    }


def example_market_tick() -> Dict[str, Any]:
    """Example MarketTick dataclass structure"""
    return {
        "instrument": "BANKNIFTY",
        "timestamp": datetime.now(timezone(timedelta(hours=5, minutes=30))),
        "last_price": 45050.0,
        "volume": 1500000
    }


# ============================================================================
# 2. OHLC BAR DATA
# ============================================================================

def example_historical_data_response() -> List[Dict[str, Any]]:
    """Example response from kite.historical_data()"""
    base_time = datetime(2024, 1, 15, 9, 15, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    
    return [
        {
            "date": base_time + timedelta(minutes=i*5),
            "open": 45000.0 + (i * 10),
            "high": 45100.0 + (i * 10),
            "low": 44950.0 + (i * 10),
            "close": 45050.0 + (i * 10),
            "volume": 1500000 + (i * 10000),
            "oi": 2500000 + (i * 5000)  # Open Interest (for F&O)
        }
        for i in range(10)
    ]


def example_ohlc_bar() -> Dict[str, Any]:
    """Example OHLCBar dataclass structure"""
    return {
        "instrument": "BANKNIFTY",
        "timeframe": "5min",
        "open": 45000.0,
        "high": 45100.0,
        "low": 44950.0,
        "close": 45050.0,
        "volume": 1500000,
        "start_at": datetime(2024, 1, 15, 9, 15, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    }


# ============================================================================
# 3. OPTIONS CHAIN DATA
# ============================================================================

def example_instruments_response() -> List[Dict[str, Any]]:
    """Example response from kite.instruments('NFO')"""
    return [
        {
            "instrument_token": 1001,
            "exchange_token": "NFO:1001",
            "tradingsymbol": "BANKNIFTY24JAN45000CE",
            "name": "BANKNIFTY",
            "last_price": 150.0,
            "expiry": date(2024, 1, 25),
            "strike": 45000.0,
            "tick_size": 0.05,
            "lot_size": 15,
            "instrument_type": "CE",
            "segment": "NFO-OPT",
            "exchange": "NFO"
        },
        {
            "instrument_token": 1002,
            "exchange_token": "NFO:1002",
            "tradingsymbol": "BANKNIFTY24JAN45000PE",
            "name": "BANKNIFTY",
            "last_price": 120.0,
            "expiry": date(2024, 1, 25),
            "strike": 45000.0,
            "tick_size": 0.05,
            "lot_size": 15,
            "instrument_type": "PE",
            "segment": "NFO-OPT",
            "exchange": "NFO"
        },
        {
            "instrument_token": 2001,
            "exchange_token": "NFO:2001",
            "tradingsymbol": "BANKNIFTY24JANFUT",
            "name": "BANKNIFTY",
            "last_price": 45050.0,
            "expiry": date(2024, 1, 25),
            "strike": 0.0,
            "tick_size": 0.05,
            "lot_size": 15,
            "instrument_type": "FUT",
            "segment": "NFO-FUT",
            "exchange": "NFO"
        }
    ]


def example_quote_response() -> Dict[str, Any]:
    """Example response from kite.quote([tokens])"""
    return {
        "1001": {  # Call option
            "last_price": 150.0,
            "oi": 10000,
            "volume": 500,
            "bid": 149.5,
            "ask": 150.5,
            "bid_qty": 100,
            "ask_qty": 100,
            "timestamp": datetime.now(timezone(timedelta(hours=5, minutes=30))),
            "greeks": {
                "delta": 0.5,
                "gamma": 0.01,
                "theta": -0.5,
                "vega": 0.2
            },
            "iv": 0.15  # Implied volatility
        },
        "1002": {  # Put option
            "last_price": 120.0,
            "oi": 8000,
            "volume": 400,
            "bid": 119.5,
            "ask": 120.5,
            "bid_qty": 100,
            "ask_qty": 100,
            "timestamp": datetime.now(timezone(timedelta(hours=5, minutes=30))),
            "greeks": {
                "delta": -0.5,
                "gamma": 0.01,
                "theta": -0.5,
                "vega": 0.2
            },
            "iv": 0.15
        },
        "2001": {  # Futures
            "last_price": 45050.0,
            "oi": 2500000,
            "volume": 1500000,
            "bid": 45049.5,
            "ask": 45050.5,
            "bid_qty": 1000,
            "ask_qty": 1000,
            "timestamp": datetime.now(timezone(timedelta(hours=5, minutes=30)))
        }
    }


def example_options_chain_response() -> Dict[str, Any]:
    """Example options chain structure returned by fetch_options_chain()"""
    return {
        "available": True,
        "futures_price": 45050.0,
        "strikes": {
            44000: {
                "ce_ltp": 1200.0,
                "pe_ltp": 800.0,
                "ce_oi": 15000,
                "pe_oi": 18000,
                "ce_volume": 5000,
                "pe_volume": 6000
            },
            44500: {
                "ce_ltp": 800.0,
                "pe_ltp": 1200.0,
                "ce_oi": 22000,
                "pe_oi": 25000,
                "ce_volume": 8000,
                "pe_volume": 9000
            },
            45000: {
                "ce_ltp": 150.0,
                "pe_ltp": 120.0,
                "ce_oi": 10000,
                "pe_oi": 8000,
                "ce_volume": 500,
                "pe_volume": 400
            },
            45500: {
                "ce_ltp": 120.0,
                "pe_ltp": 800.0,
                "ce_oi": 8000,
                "pe_oi": 22000,
                "ce_volume": 400,
                "pe_volume": 8000
            },
            46000: {
                "ce_ltp": 800.0,
                "pe_ltp": 1200.0,
                "ce_oi": 18000,
                "pe_oi": 25000,
                "ce_volume": 6000,
                "pe_volume": 9000
            }
        }
    }


# ============================================================================
# 4. ACCOUNT/MARGINS DATA
# ============================================================================

def example_margins_response() -> Dict[str, Any]:
    """Example response from kite.margins()"""
    return {
        "equity": {
            "enabled": True,
            "net": 100000.0,
            "available": {
                "cash": 95000.0,
                "opening_balance": 100000.0,
                "live_balance": 95000.0,
                "collateral": 0.0,
                "intraday_payin": 0.0
            },
            "utilised": {
                "debits": 5000.0,
                "exposure": 3000.0,
                "m2m_unrealised": 1000.0,
                "m2m_realised": 500.0,
                "option_premium": 500.0,
                "span": 2000.0,
                "adhoc_margin": 0.0,
                "notional_cash": 0.0
            }
        },
        "commodity": {
            "enabled": False,
            "net": 0.0,
            "available": {},
            "utilised": {}
        }
    }


# ============================================================================
# 5. PROFILE DATA
# ============================================================================

def example_profile_response() -> Dict[str, Any]:
    """Example response from kite.profile()"""
    return {
        "user_id": "AB1234",
        "user_name": "John Doe",
        "user_shortname": "JD",
        "email": "john@example.com",
        "user_type": "investor",
        "broker": "ZERODHA",
        "exchanges": ["NSE", "BSE", "NFO", "CDS", "MCX"],
        "products": ["CNC", "MIS", "NRML"],
        "avatar_url": "https://...",
        "meta": {}
    }


# ============================================================================
# 6. POSITIONS DATA
# ============================================================================

def example_positions_response() -> Dict[str, Any]:
    """Example response from kite.positions()"""
    return {
        "net": [
            {
                "tradingsymbol": "BANKNIFTY24JAN45000CE",
                "exchange": "NFO",
                "instrument_token": 1001,
                "product": "MIS",
                "quantity": 15,
                "average_price": 150.0,
                "last_price": 155.0,
                "pnl": 75.0,  # (155 - 150) * 15
                "m2m": 75.0,
                "buy_quantity": 15,
                "sell_quantity": 0
            }
        ],
        "day": [
            {
                "tradingsymbol": "BANKNIFTY24JAN45000CE",
                "exchange": "NFO",
                "instrument_token": 1001,
                "product": "MIS",
                "quantity": 15,
                "average_price": 150.0,
                "last_price": 155.0,
                "pnl": 75.0,
                "m2m": 75.0,
                "buy_quantity": 15,
                "sell_quantity": 0
            }
        ]
    }


# ============================================================================
# 7. ORDERS DATA
# ============================================================================

def example_orders_response() -> List[Dict[str, Any]]:
    """Example response from kite.orders()"""
    return [
        {
            "order_id": "240115000012345",
            "exchange_order_id": "NFO123456",
            "tradingsymbol": "BANKNIFTY24JAN45000CE",
            "instrument_token": 1001,
            "transaction_type": "BUY",
            "product": "MIS",
            "order_type": "LIMIT",
            "quantity": 15,
            "price": 150.0,
            "trigger_price": 0.0,
            "status": "COMPLETE",
            "filled_quantity": 15,
            "pending_quantity": 0,
            "order_timestamp": datetime.now(timezone(timedelta(hours=5, minutes=30))),
            "exchange_timestamp": datetime.now(timezone(timedelta(hours=5, minutes=30)))
        },
        {
            "order_id": "240115000012346",
            "exchange_order_id": "NFO123457",
            "tradingsymbol": "BANKNIFTY24JAN45000PE",
            "instrument_token": 1002,
            "transaction_type": "SELL",
            "product": "MIS",
            "order_type": "MARKET",
            "quantity": 15,
            "price": 0.0,
            "trigger_price": 0.0,
            "status": "OPEN",
            "filled_quantity": 0,
            "pending_quantity": 15,
            "order_timestamp": datetime.now(timezone(timedelta(hours=5, minutes=30))),
            "exchange_timestamp": None
        }
    ]


# ============================================================================
# HELPER FUNCTIONS FOR HISTORICAL SIMULATION
# ============================================================================

def generate_historical_ticks(
    start_time: datetime,
    end_time: datetime,
    base_price: float = 45000.0,
    interval_seconds: int = 5
) -> List[Dict[str, Any]]:
    """Generate a list of historical tick data for simulation."""
    ticks = []
    current_time = start_time
    price = base_price
    
    while current_time <= end_time:
        # Simple random walk for price simulation
        import random
        price_change = random.uniform(-10, 10)
        price = max(1000, price + price_change)  # Ensure price doesn't go negative
        
        ticks.append({
            "instrument": "BANKNIFTY",
            "timestamp": current_time,
            "last_price": round(price, 2),
            "volume": random.randint(1000, 10000)
        })
        
        current_time += timedelta(seconds=interval_seconds)
    
    return ticks


def generate_historical_ohlc(
    start_date: date,
    end_date: date,
    base_price: float = 45000.0,
    timeframe: str = "5min"
) -> List[Dict[str, Any]]:
    """Generate a list of historical OHLC data for simulation."""
    bars = []
    current_date = start_date
    price = base_price
    
    # Parse timeframe
    if timeframe == "5min":
        delta = timedelta(minutes=5)
        start_time = datetime.combine(current_date, datetime.min.time().replace(hour=9, minute=15))
    elif timeframe == "1day":
        delta = timedelta(days=1)
        start_time = datetime.combine(current_date, datetime.min.time())
    else:
        delta = timedelta(minutes=1)
        start_time = datetime.combine(current_date, datetime.min.time().replace(hour=9, minute=15))
    
    start_time = start_time.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
    current_time = start_time
    
    while current_time.date() <= end_date:
        import random
        
        # Generate OHLC for this bar
        open_price = price
        high_price = open_price + random.uniform(0, 50)
        low_price = open_price - random.uniform(0, 50)
        close_price = random.uniform(low_price, high_price)
        volume = random.randint(100000, 2000000)
        
        bars.append({
            "instrument": "BANKNIFTY",
            "timeframe": timeframe,
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(close_price, 2),
            "volume": volume,
            "start_at": current_time
        })
        
        price = close_price  # Next bar starts where this one closed
        current_time += delta
    
    return bars


if __name__ == "__main__":
    """Print examples of all data structures."""
    print("=" * 80)
    print("ZERODHA DATA STRUCTURE EXAMPLES")
    print("=" * 80)
    
    print("\n1. LTP Response:")
    print(example_ltp_response())
    
    print("\n2. Market Tick:")
    print(example_market_tick())
    
    print("\n3. Historical Data (first 2 candles):")
    print(example_historical_data_response()[:2])
    
    print("\n4. OHLC Bar:")
    print(example_ohlc_bar())
    
    print("\n5. Instruments (NFO):")
    print(example_instruments_response())
    
    print("\n6. Quote Response:")
    print(example_quote_response())
    
    print("\n7. Options Chain:")
    print(example_options_chain_response())
    
    print("\n8. Margins:")
    print(example_margins_response())
    
    print("\n9. Profile:")
    print(example_profile_response())
    
    print("\n10. Positions:")
    print(example_positions_response())
    
    print("\n11. Orders:")
    print(example_orders_response())
    
    print("\n" + "=" * 80)
    print("Use these structures as templates for historical simulation!")
    print("=" * 80)


