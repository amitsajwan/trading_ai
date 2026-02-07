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
# Note: market_data is mounted as volume for development
# Force rebuild marker: 2026-01-30-02:45
COPY requirements.txt .
COPY config.py .
COPY *.py .
COPY *.json .
COPY *.md .
COPY logs/ logs/
COPY docs/ docs/
COPY scripts/ scripts/
COPY services/ services/
COPY dashboard/ dashboard/
COPY engine_module/ engine_module/
COPY news_module/ news_module/
COPY risk_module/ risk_module/
COPY backtesting_module/ backtesting_module/
COPY market_data/ market_data/
COPY redis_ws_gateway/ redis_ws_gateway/
COPY genai_module/ genai_module/
COPY core_kernel/ core_kernel/

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/backtesting_module /app/engine_module

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/dashboard:/app/engine_module/src:/app/risk_module/src:/app/market_data/src:/app/news_module/src:/app/redis_ws_gateway:/app/genai_module/src:/app/core_kernel/src
ENV PYTHONHASHSEED=0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import engine_module.src.engine_module.orchestrator_stub; print('healthy')" || exit 1

# Default command (can be overridden)
CMD ["python", "-m", "services.trading_service"]

