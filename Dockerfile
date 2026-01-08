FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (updated 2026-01-07 for modular architecture)
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/backtesting_module /app/engine_module

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/engine_module/src:/app/risk_module/src:/app/market_data/src:/app/news_module/src
ENV PYTHONHASHSEED=0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import engine_module.src.engine_module.orchestrator_stub; print('healthy')" || exit 1

# Default command (can be overridden)
CMD ["python", "-m", "services.trading_service"]

