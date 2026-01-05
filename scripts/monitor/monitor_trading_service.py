"""Monitor trading service startup and loop execution with detailed tracing."""
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import io

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,  # Most verbose
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    force=True
)

logger = logging.getLogger(__name__)

async def monitor_service():
    """Monitor the trading service startup and loop."""
    print("=" * 70)
    print("TRADING SERVICE MONITOR - Detailed Trace")
    print("=" * 70)
    print(f"Start time: {datetime.now()}")
    print()
    
    try:
        from services.trading_service import TradingService
        from core_kernel.config.settings import settings
        
        print("[OK] Step 1: Imports successful")
        print(f"   - Data source: {settings.data_source}")
        print(f"   - Instrument: {settings.instrument_name} ({settings.instrument_symbol})")
        print()
        
        print("[OK] Step 2: Creating TradingService instance...")
        service = TradingService(kite=None)
        print(f"   - Service created: {service}")
        print(f"   - Running flag: {service.running}")
        print()
        
        print("[OK] Step 3: Initializing service...")
        try:
            await service.initialize()
            print("   [OK] Initialization completed")
            print(f"   - Trading graph: {service.trading_graph is not None}")
            print(f"   - Market memory: {service.market_memory is not None}")
            print(f"   - Macro fetcher: {service.macro_fetcher}")
        except Exception as e:
            print(f"   [FAIL] Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return
        print()
        
        print("[OK] Step 4: Starting service (will run for 90 seconds to observe loop)...")
        print("=" * 70)
        
        # Start the service in background
        service.running = True
        
        # Create the trading loop task manually to monitor it
        print("Creating trading loop task...")
        loop_task = asyncio.create_task(service._trading_loop())
        print("[OK] Trading loop task created")
        print()
        
        # Also start other components
        if hasattr(service, 'position_monitor') and service.position_monitor:
            print("Starting position monitor...")
            service.position_monitor_task = asyncio.create_task(service.position_monitor.start())
            print("[OK] Position monitor started")
        
        print()
        print("=" * 70)
        print("MONITORING LOOP EXECUTION")
        print("=" * 70)
        print("Waiting 90 seconds to observe loop behavior...")
        print("You should see [LOOP #] messages below:")
        print("=" * 70)
        print()
        
        # Wait and monitor
        try:
            await asyncio.wait_for(loop_task, timeout=90.0)
        except asyncio.TimeoutError:
            print()
            print("=" * 70)
            print("[TIMEOUT] Monitor timeout reached (90 seconds)")
            print("=" * 70)
            service.running = False
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                print("[OK] Loop cancelled successfully")
        
        print()
        print("=" * 70)
        print("MONITORING COMPLETE")
        print("=" * 70)
        
    except Exception as e:
        print(f"[FAIL] Error in monitor: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(monitor_service())

