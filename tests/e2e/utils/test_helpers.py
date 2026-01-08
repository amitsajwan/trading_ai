"""Helper utilities for E2E tests."""

from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
import asyncio


def generate_historical_ticks(
    start_date: date,
    end_date: date,
    base_price: float = 45000.0,
    interval_minutes: int = 1
) -> List[Dict[str, Any]]:
    """Generate historical tick data for testing.
    
    Args:
        start_date: Start date for data generation
        end_date: End date for data generation
        base_price: Starting price
        interval_minutes: Minutes between ticks
        
    Returns:
        List of tick dictionaries
    """
    ticks = []
    current = datetime.combine(start_date, datetime.min.time())
    end = datetime.combine(end_date, datetime.max.time())
    
    price = base_price
    while current <= end:
        # Simulate price movement with slight trend
        price_change = (price * 0.0001)  # 0.01% movement
        price += price_change
        
        ticks.append({
            "instrument": "NIFTY BANK",
            "timestamp": current,
            "last_price": price,
            "volume": 1000000 + int(price_change * 100)
        })
        
        current += timedelta(minutes=interval_minutes)
    
    return ticks


def generate_ohlc_bars(
    start_date: date,
    end_date: date,
    base_price: float = 45000.0,
    timeframe: str = "1min"
) -> List[Dict[str, Any]]:
    """Generate OHLC bar data for testing.
    
    Args:
        start_date: Start date for data generation
        end_date: End date for data generation
        base_price: Starting price
        timeframe: Bar timeframe (1min, 5min, etc.)
        
    Returns:
        List of OHLC bar dictionaries
    """
    bars = []
    current = datetime.combine(start_date, datetime.min.time())
    end = datetime.combine(end_date, datetime.max.time())
    
    price = base_price
    minutes_per_bar = int(timeframe.replace("min", "")) if "min" in timeframe else 1
    
    while current <= end:
        bars.append({
            "instrument": "NIFTY BANK",
            "timeframe": timeframe,
            "open": price,
            "high": price + 100,
            "low": price - 100,
            "close": price + 50,
            "volume": 1000000,
            "start_at": current
        })
        
        price += 10  # Slight upward trend
        current += timedelta(minutes=minutes_per_bar)
    
    return bars


def create_test_signal(
    action: str = "BUY",
    symbol: str = "NIFTY BANK",
    confidence: float = 0.75,
    execution_type: str = "conditional",
    conditions: Optional[Dict] = None
) -> Dict[str, Any]:
    """Create a test trading signal.
    
    Args:
        action: BUY, SELL, or HOLD
        symbol: Instrument symbol
        confidence: Signal confidence (0-1)
        execution_type: immediate or conditional
        conditions: Conditional execution conditions
        
    Returns:
        Signal dictionary
    """
    signal_id = f"test_signal_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    
    if conditions is None:
        conditions = {
            "rsi_14": {"operator": ">", "threshold": 32.0}
        }
    
    return {
        "id": signal_id,
        "symbol": symbol,
        "action": action,
        "agent_name": "test_agent",
        "confidence": confidence,
        "entry_price": 45000.0,
        "stop_loss": 44800.0,
        "take_profit": 45300.0,
        "quantity": 25,
        "status": "pending",
        "execution_type": execution_type,
        "conditions": conditions,
        "created_at": datetime.now().isoformat()
    }


def create_test_trade(
    action: str = "BUY",
    symbol: str = "NIFTY BANK",
    quantity: int = 25,
    price: float = 45000.0
) -> Dict[str, Any]:
    """Create a test trade.
    
    Args:
        action: BUY or SELL
        symbol: Instrument symbol
        quantity: Trade quantity
        price: Execution price
        
    Returns:
        Trade dictionary
    """
    trade_id = f"test_trade_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    
    return {
        "id": trade_id,
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "price": price,
        "executed_at": datetime.now().isoformat(),
        "status": "executed"
    }


async def wait_for_condition(
    condition_func,
    timeout: float = 10.0,
    interval: float = 0.1,
    error_message: str = "Condition not met within timeout"
) -> bool:
    """Wait for a condition to become true.
    
    Args:
        condition_func: Async function that returns bool
        timeout: Maximum time to wait (seconds)
        interval: Check interval (seconds)
        error_message: Error message if timeout
        
    Returns:
        True if condition met, raises TimeoutError otherwise
    """
    start_time = asyncio.get_event_loop().time()
    
    while True:
        if await condition_func():
            return True
        
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout:
            raise TimeoutError(f"{error_message} (timeout: {timeout}s)")
        
        await asyncio.sleep(interval)


def validate_api_response(
    response: Any,
    expected_status: int = 200,
    required_fields: Optional[List[str]] = None
) -> tuple[bool, List[str]]:
    """Validate API response structure.
    
    Args:
        response: API response object
        expected_status: Expected HTTP status code
        required_fields: List of required field names
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Check status code
    if hasattr(response, "status_code"):
        if response.status_code != expected_status:
            errors.append(f"Expected status {expected_status}, got {response.status_code}")
    
    # Check response data
    if hasattr(response, "json"):
        try:
            data = response.json()
        except Exception as e:
            errors.append(f"Cannot parse JSON response: {e}")
            return False, errors
    else:
        data = response
    
    # Check required fields
    if required_fields:
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
    
    return len(errors) == 0, errors


def compare_floats(a: float, b: float, tolerance: float = 0.01) -> bool:
    """Compare two floats with tolerance.
    
    Args:
        a: First float
        b: Second float
        tolerance: Allowed difference
        
    Returns:
        True if values are within tolerance
    """
    return abs(a - b) <= tolerance


