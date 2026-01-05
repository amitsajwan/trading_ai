# Production Deployment Guide

## Overview

This guide covers deploying the GenAI Trading System to production environments with proper security, monitoring, and scalability considerations.

## Prerequisites

### Infrastructure Requirements

- **Docker**: Version 24.0+ with Docker Compose
- **Kubernetes**: Optional, for advanced scaling
- **Cloud Provider**: AWS, GCP, or Azure recommended
- **Domain**: SSL certificate for HTTPS

### System Requirements

- **CPU**: 4+ cores (8+ recommended)
- **RAM**: 8GB minimum (16GB+ recommended)
- **Storage**: 100GB SSD for databases
- **Network**: Stable internet connection (100Mbps+)

## Docker Production Setup

### 1. Environment Configuration

Create production environment files:

```bash
# Production .env file
cp .env.btc .env.production
# Edit with production API keys and settings
```

**Production .env settings:**
```bash
# Trading Mode
PAPER_TRADING_MODE=false

# Database
MONGODB_URI=mongodb://mongodb:27017/zerodha_trading
REDIS_HOST=redis

# Security
SECRET_KEY=your-256-bit-secret-key-here
API_KEY=your-api-key-for-external-access

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true

# Performance
LLM_MAX_CONCURRENCY=3
REDIS_CONNECTION_POOL_SIZE=20
```

### 2. Docker Compose Production

**docker-compose.prod.yml:**
```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:7
    container_name: zerodha-mongodb-prod
    restart: always
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=${MONGO_ROOT_PASSWORD}
      - MONGO_INITDB_DATABASE=zerodha_trading
    volumes:
      - mongo_prod_data:/data/db
      - ./mongo-init:/docker-entrypoint-initdb.d
    ports:
      - "127.0.0.1:27017:27017"  # Bind to localhost only
    networks:
      - trading-prod
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: zerodha-redis-prod
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_prod_data:/data
    ports:
      - "127.0.0.1:6379:6379"
    networks:
      - trading-prod
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  trading-system:
    build:
      context: .
      dockerfile: Dockerfile.prod
    container_name: zerodha-trading-prod
    restart: always
    env_file:
      - .env.production
    environment:
      - ENVIRONMENT=production
    depends_on:
      mongodb:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - ./credentials.json:/app/credentials.json:ro
    ports:
      - "127.0.0.1:8888:8888"
    networks:
      - trading-prod
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8888/health"]
      interval: 60s
      timeout: 10s
      retries: 3

networks:
  trading-prod:
    driver: bridge

volumes:
  mongo_prod_data:
    driver: local
  redis_prod_data:
    driver: local
```

### 3. Production Dockerfile

**Dockerfile.prod:**
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8888/health || exit 1

# Expose port
EXPOSE 8888

# Start application
CMD ["python", "dashboard_pro.py"]
```

## Security Hardening

### 1. Network Security

**Firewall Configuration:**
```bash
# Allow only necessary ports
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80
ufw allow 443
ufw --force enable
```

**Docker Network Isolation:**
```yaml
# Use internal networks
networks:
  trading-prod:
    internal: true  # No external access to containers
```

### 2. API Security

**Add Authentication Middleware:**
```python
# middleware/auth.py
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        response = await call_next(request)
        return response
```

**Enable HTTPS:**
```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Data Protection

**Database Encryption:**
```javascript
// MongoDB encryption
db.createEncryptionKey()
db.getCollection().createIndex(
    { "encryptedField": 1 },
    { "encryptedFields": {
        "encryptedField": {
            "keyId": UUID("..."),
            "algorithm": "AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic"
        }
    }}
)
```

**Backup Security:**
```bash
# Encrypted backups
mongodump --db zerodha_trading --out /backup --username admin --password $MONGO_PASSWORD
tar -czf backup.tar.gz /backup
openssl enc -aes-256-cbc -salt -in backup.tar.gz -out backup.enc -k $BACKUP_KEY
```

## Monitoring and Alerting

### 1. Application Monitoring

**Prometheus Metrics:**
```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge

REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
RESPONSE_TIME = Histogram('api_response_time_seconds', 'Response time', ['endpoint'])
ACTIVE_POSITIONS = Gauge('active_positions', 'Number of active positions')
PNL_GAUGE = Gauge('current_pnl', 'Current P&L')
```

**Grafana Dashboard:**
- API response times
- Error rates
- Trading performance
- System resource usage
- Agent analysis times

### 2. Alerting Rules

**Critical Alerts:**
```yaml
# alert_rules.yml
groups:
  - name: trading_alerts
    rules:
      - alert: TradingSystemDown
        expr: up{job="trading-system"} == 0
        for: 5m
        labels:
          severity: critical

      - alert: HighErrorRate
        expr: rate(http_requests_total{status="500"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning

      - alert: LargeDrawdown
        expr: trading_pnl_percentage < -5
        for: 10m
        labels:
          severity: critical
```

### 3. Logging

**Structured Logging:**
```python
# logging_config.py
import logging
from pythonjsonlogger import jsonlogger

logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(name)s %(levelname)s %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

**Log Aggregation:**
```yaml
# docker-compose.logging.yml
services:
  logstash:
    image: docker.elastic.co/logstash/logstash:8.6.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    ports:
      - "5044:5044"

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.6.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"

  kibana:
    image: docker.elastic.co/kibana/kibana:8.6.0
    ports:
      - "5601:5601"
```

## Backup and Recovery

### 1. Database Backups

**Automated Backup Script:**
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
MONGO_HOST="localhost"
MONGO_PORT="27017"

# MongoDB backup
mongodump --host $MONGO_HOST --port $MONGO_PORT \
          --db zerodha_trading \
          --out $BACKUP_DIR/mongodb_$DATE

# Redis backup
redis-cli -h localhost -p 6379 --rdb $BACKUP_DIR/redis_$DATE.rdb

# Compress and encrypt
tar -czf $BACKUP_DIR/backup_$DATE.tar.gz $BACKUP_DIR/mongodb_$DATE $BACKUP_DIR/redis_$DATE.rdb
openssl enc -aes-256-cbc -salt -in $BACKUP_DIR/backup_$DATE.tar.gz \
           -out $BACKUP_DIR/backup_$DATE.enc -k $ENCRYPTION_KEY

# Cleanup old backups
find $BACKUP_DIR -name "backup_*.enc" -mtime +30 -delete
```

**Schedule Backups:**
```bash
# Add to crontab
0 2 * * * /path/to/backup.sh  # Daily at 2 AM
```

### 2. Disaster Recovery

**Recovery Procedure:**
```bash
#!/bin/bash
# restore.sh
BACKUP_FILE=$1

# Decrypt and extract
openssl enc -d -aes-256-cbc -in $BACKUP_FILE -out backup.tar.gz -k $ENCRYPTION_KEY
tar -xzf backup.tar.gz

# Restore MongoDB
mongorestore --db zerodha_trading --drop mongodb_backup/

# Restore Redis
redis-cli -h localhost -p 6379 --rdb redis_backup.rdb

# Restart services
docker-compose restart trading-system
```

## Scaling Strategies

### 1. Horizontal Scaling

**Multiple Trading Instances:**
```yaml
# docker-compose.scale.yml
services:
  trading-system-1:
    extends: trading-system
    container_name: zerodha-trading-1
    ports:
      - "127.0.0.1:8888:8888"

  trading-system-2:
    extends: trading-system
    container_name: zerodha-trading-2
    ports:
      - "127.0.0.1:8889:8888"

  load-balancer:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

### 2. Database Scaling

**MongoDB Replica Set:**
```yaml
services:
  mongodb-primary:
    image: mongo:7
    command: --replSet rs0 --bind_ip_all
    # ... other config

  mongodb-secondary-1:
    image: mongo:7
    command: --replSet rs0 --bind_ip_all
    depends_on:
      - mongodb-primary

  mongodb-secondary-2:
    image: mongo:7
    command: --replSet rs0 --bind_ip_all
    depends_on:
      - mongodb-primary
```

### 3. Kubernetes Deployment

**K8s Manifest:**
```yaml
# k8s/deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: trading-system
  template:
    metadata:
      labels:
        app: trading-system
    spec:
      containers:
      - name: trading
        image: zerodha-trading:latest
        ports:
        - containerPort: 8888
        envFrom:
        - configMapRef:
            name: trading-config
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8888
          initialDelaySeconds: 30
          periodSeconds: 10
```

## Performance Optimization

### 1. Database Optimization

**Indexing Strategy:**
```javascript
// MongoDB indexes
db.ohlc_history.createIndex({timestamp: -1, instrument: 1})
db.ohlc_history.createIndex({instrument: 1, timeframe: 1})
db.trades_executed.createIndex({entry_timestamp: -1})
db.agent_decisions.createIndex({timestamp: -1, instrument: 1})
```

**Query Optimization:**
```python
# Use projections to limit data transfer
projection = {"_id": 0, "timestamp": 1, "close": 1, "volume": 1}
ohlc_data = collection.find(query, projection).limit(100)
```

### 2. Caching Strategy

**Multi-Level Caching:**
```python
# Redis cache hierarchy
# Level 1: Hot data (5min TTL)
redis.setex(f"price:{instrument}:latest", 300, price)

# Level 2: Warm data (1h TTL)
redis.setex(f"ohlc:{instrument}:1h:{timestamp}", 3600, ohlc_json)

# Level 3: Cold data (24h TTL)
redis.setex(f"ohlc:{instrument}:daily:{timestamp}", 86400, daily_ohlc)
```

### 3. LLM Optimization

**Provider Fallback Chain:**
```python
PROVIDER_CHAIN = [
    {"name": "groq", "priority": 1, "cost_per_token": 0.0001},
    {"name": "openai", "priority": 2, "cost_per_token": 0.0002},
    {"name": "google", "priority": 3, "cost_per_token": 0.00015}
]
```

**Response Caching:**
```python
# Cache LLM responses for similar prompts
cache_key = hashlib.md5(prompt.encode()).hexdigest()
cached_response = redis.get(f"llm_cache:{cache_key}")
if cached_response:
    return json.loads(cached_response)
```

## Maintenance Procedures

### 1. Rolling Updates

**Zero-Downtime Deployment:**
```bash
# Update with rolling restart
docker-compose up -d --no-deps trading-system

# Health check
curl -f http://localhost:8888/health

# If healthy, continue with other services
docker-compose up -d
```

### 2. Log Rotation

**Logrotate Configuration:**
```bash
# /etc/logrotate.d/trading-system
/app/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    create 644 app app
    postrotate
        docker-compose exec trading-system kill -HUP 1
    endscript
}
```

### 3. Security Updates

**Automated Updates:**
```bash
# Update Docker images
docker-compose pull
docker-compose up -d

# Update Python packages
pip install --upgrade -r requirements.txt

# Security scanning
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    clair-scanner --ip 127.0.0.1 zerodha-trading:latest
```

## Troubleshooting Production

### Common Issues

1. **Memory Leaks**
   - Monitor with `docker stats`
   - Implement garbage collection tuning
   - Restart containers periodically

2. **Database Connection Pool Exhaustion**
   - Increase connection pool size
   - Implement connection pooling
   - Monitor connection usage

3. **API Rate Limiting**
   - Implement exponential backoff
   - Cache API responses
   - Upgrade API plans

4. **High Latency**
   - Optimize database queries
   - Implement response compression
   - Use CDN for static assets

### Emergency Procedures

**System Halt:**
```bash
# Immediate stop all trading
docker-compose exec trading-system curl -X POST http://localhost:8888/api/trading/pause

# Close all positions manually
# Check positions via API
curl http://localhost:8888/api/positions

# Emergency restart
docker-compose restart
```

**Data Recovery:**
```bash
# Restore from backup
./restore.sh /backups/backup_20240101.enc

# Verify data integrity
mongosh zerodha_trading --eval "db.stats()"

# Restart with reduced position sizes
PAPER_TRADING_MODE=true docker-compose up -d
```