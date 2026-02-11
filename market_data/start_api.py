#!/usr/bin/env python3
"""Start Market Data API Service.

This script ensures the API starts from the correct directory with proper paths.
"""
import os
import sys

# Change to market_data directory (parent of src)
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Load .env file first
try:
    from dotenv import load_dotenv
    env_file = os.path.join(script_dir, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"Loaded environment from: {env_file}")
except ImportError:
    print("Warning: python-dotenv not installed. Using system environment only.")

# Set default mode to live for API
if not os.getenv("MODE"):
    os.environ["MODE"] = "live"
    print("Set MODE=live (default for API)")

# Now change to src directory
src_dir = os.path.join(script_dir, "src")
os.chdir(src_dir)

# Add src to Python path
sys.path.insert(0, src_dir)

# Import and run uvicorn
if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8004"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"  # Disable reload for stability
    
    print(f"Starting API server on {host}:{port}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Redis: {os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}")
    print(f"Instrument: {os.getenv('INSTRUMENT_SYMBOL', 'Not set')}")
    print("")
    
    # Start the server
    uvicorn.run(
        "market_data.api_service:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
