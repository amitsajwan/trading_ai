"""Test if trading loop logging is working."""
import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging to see all messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)

from services.trading_service import TradingService
from config.settings import settings

async def test_loop():
    """Test if the trading loop starts and logs properly."""
    print("=" * 70)
    print("Testing Trading Loop Logging")
    print("=" * 70)
    print()
    
    print("Creating trading service...")
    service = TradingService(kite=None)
    
    print("Initializing service...")
    try:
        await service.initialize()
        print("✅ Service initialized")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return
    
    print()
    print("Starting trading loop (will run for 70 seconds to see one full cycle)...")
    print("=" * 70)
    
    # Start the loop
    service.running = True
    loop_task = asyncio.create_task(service._trading_loop())
    
    # Wait 70 seconds to see one full cycle
    try:
        await asyncio.wait_for(loop_task, timeout=70.0)
    except asyncio.TimeoutError:
        print()
        print("=" * 70)
        print("⏰ Test timeout reached (70 seconds)")
        print("This is expected - cancelling loop...")
        print("=" * 70)
        service.running = False
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
    
    print()
    print("=" * 70)
    print("Test Complete")
    print("=" * 70)
    print("If you saw [LOOP #] messages above, logging is working!")
    print("If not, there may be an issue with the loop starting.")

if __name__ == "__main__":
    asyncio.run(test_loop())

