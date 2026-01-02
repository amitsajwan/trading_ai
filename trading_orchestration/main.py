"""Main entry point for trading graph execution."""

import logging
import json
from pathlib import Path
from kiteconnect import KiteConnect
import sys
from pathlib import Path
# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from trading_orchestration.trading_graph import TradingGraph
from data.market_memory import MarketMemory
from data.ingestion_service import DataIngestionService
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_kite_credentials() -> dict:
    """Load Kite credentials from credentials.json."""
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        raise FileNotFoundError("credentials.json not found. Run auto_login.py first.")
    
    with open(cred_path) as f:
        return json.load(f)


def main():
    """Main entry point."""
    try:
        # Load credentials
        creds = load_kite_credentials()
        
        # Initialize Kite Connect
        kite = KiteConnect(api_key=creds["api_key"])
        kite.set_access_token(creds["access_token"])
        logger.info("Kite Connect initialized")
        
        # Initialize market memory
        market_memory = MarketMemory()
        logger.info("Market memory initialized")
        
        # Initialize data ingestion (optional - can run separately)
        # ingestion_service = DataIngestionService(kite, market_memory)
        # ingestion_service.start()
        
        # Initialize trading graph
        trading_graph = TradingGraph(kite=kite, market_memory=market_memory)
        logger.info("Trading graph initialized")
        
        # Run trading graph
        result = trading_graph.run()
        
        # Print results
        print("\n=== Trading Decision ===")
        signal_str = result.final_signal.value if hasattr(result.final_signal, 'value') else str(result.final_signal)
        print(f"Signal: {signal_str}")
        print(f"Position Size: {result.position_size}")
        print(f"Entry Price: {result.entry_price}")
        print(f"Stop Loss: {result.stop_loss}")
        print(f"Take Profit: {result.take_profit}")
        print(f"\nAgent Explanations:")
        for explanation in result.agent_explanations:
            print(f"  - {explanation}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()