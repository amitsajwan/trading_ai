"""Main entry point for Redis WebSocket Gateway."""

import logging
import sys
import uvicorn
from redis_ws_gateway.gateway import app, GATEWAY_HOST, GATEWAY_PORT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Run the Redis WebSocket Gateway server."""
    logger.info(f"Starting Redis WebSocket Gateway on {GATEWAY_HOST}:{GATEWAY_PORT}")
    
    uvicorn.run(
        app,
        host=GATEWAY_HOST,
        port=GATEWAY_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
