#!/usr/bin/env python3
"""Startup script for news API service."""

import os
import sys

# Set environment variables
os.environ.setdefault("USE_YFINANCE_NEWS", "false")
os.environ.setdefault("NEWS_API_PORT", "8007")
os.environ.setdefault("NEWS_API_HOST", "0.0.0.0")

# Import and run
from news_module.api_service import app
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("NEWS_API_PORT", "8007"))
    host = os.getenv("NEWS_API_HOST", "0.0.0.0")
    
    print(f"Starting News API on {host}:{port}")
    uvicorn.run(app, host=host, port=port)