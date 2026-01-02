# Production Deployment Guide

This guide covers deploying the GenAI Trading System to production.

## Prerequisites

- Docker and Docker Compose installed
- MongoDB (local or Atlas)
- Redis (local or cloud)
- Zerodha Kite Connect API credentials
- Groq API key (or OpenAI/Azure OpenAI)
- Slack webhook URL (optional, for alerts)

## Quick Start with Docker

### 1. Environment Setup

Create a `.env` file in the project root:

```bash
# LLM Configuration
GROQ_API_KEY=your_groq_api_key
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile

# Zerodha API
KITE_API_KEY=your_kite_api_key
KITE_API_SECRET=your_kite_api_secret

# Databases
MONGODB_URI=mongodb://mongodb:27017/
MONGODB_DB_NAME=zerodha_trading
REDIS_HOST=redis
REDIS_PORT=6379

# Trading Configuration
PAPER_TRADING_MODE=true
MARKET_OPEN_TIME=09:15:00
MARKET_CLOSE_TIME=15:30:00

# Monitoring
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
ENABLE_ALERTS=true

# News API (Optional)
NEWS_API_KEY=your_news_api_key
```

### 2. Zerodha Authentication

Before starting the system, authenticate with Zerodha:

```bash
python auto_login.py
```

This creates `credentials.json` which will be mounted into the Docker container.

### 3. Start Services

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f trading-bot
```

### 4. Initialize MongoDB Schema

```bash
# Run inside container or locally
docker-compose exec trading-bot python mongodb_schema.py
```

## Production Deployment

### AWS EC2 Deployment

1. **Launch EC2 Instance**
   - Ubuntu 22.04 LTS
   - t3.medium or larger
   - Security group: Allow ports 22, 8000 (for dashboard)

2. **Install Docker**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

3. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd zerodha
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   nano .env  # Edit with production values
   ```

5. **Start Services**
   ```bash
   docker-compose up -d
   ```

6. **Setup Systemd Service** (Optional)
   ```bash
   sudo nano /etc/systemd/system/trading-bot.service
   ```
   
   Content:
   ```ini
   [Unit]
   Description=Trading Bot Service
   After=docker.service
   Requires=docker.service
   
   [Service]
   Type=oneshot
   RemainAfterExit=yes
   WorkingDirectory=/path/to/zerodha
   ExecStart=/usr/bin/docker-compose up -d
   ExecStop=/usr/bin/docker-compose down
   
   [Install]
   WantedBy=multi-user.target
   ```

### MongoDB Atlas Setup

1. Create MongoDB Atlas cluster (M0 free tier or M2+)
2. Get connection string
3. Update `.env`:
   ```
   MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
   ```

### Redis Cloud Setup

1. Create Redis Cloud account
2. Create database
3. Update `.env`:
   ```
   REDIS_HOST=your-redis-host.redis.cloud
   REDIS_PORT=12345
   REDIS_PASSWORD=your-password
   ```

## Monitoring

### Dashboard Access

The FastAPI dashboard runs on port 8000:

```bash
# Access locally
http://localhost:8000

# Or expose via nginx reverse proxy
```

### Health Checks

```bash
# System health
curl http://localhost:8000/health

# Trading metrics
curl http://localhost:8000/metrics/trading

# Agent metrics
curl http://localhost:8000/metrics/agents
```

### Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f trading-bot

# View last 100 lines
docker-compose logs --tail=100 trading-bot
```

## Backup & Recovery

### MongoDB Backup

```bash
# Backup
docker-compose exec mongodb mongodump --out /data/backup

# Restore
docker-compose exec mongodb mongorestore /data/backup
```

### Automated Backups

Add to crontab:
```bash
0 2 * * * docker-compose exec mongodb mongodump --out /data/backup/$(date +\%Y\%m\%d)
```

## Scaling

### Horizontal Scaling

For high-frequency trading, run multiple instances:

1. Use Redis for shared state
2. Use MongoDB for shared trade logs
3. Run multiple trading-bot containers with different instance IDs

### Vertical Scaling

Increase resources:
- MongoDB: More RAM for larger datasets
- Redis: More memory for hot data
- Trading Bot: More CPU for faster agent processing

## Security

### API Keys

- Never commit `.env` file
- Use secrets management (AWS Secrets Manager, HashiCorp Vault)
- Rotate API keys regularly

### Network Security

- Use VPN for database access
- Restrict MongoDB/Redis to internal network
- Use SSL/TLS for all external connections

### Access Control

- Limit SSH access to trading server
- Use key-based authentication
- Enable firewall rules

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs trading-bot

# Check environment variables
docker-compose exec trading-bot env | grep GROQ

# Restart services
docker-compose restart
```

### MongoDB Connection Issues

```bash
# Test connection
docker-compose exec trading-bot python -c "from mongodb_schema import get_mongo_client; get_mongo_client()"

# Check MongoDB logs
docker-compose logs mongodb
```

### Redis Connection Issues

```bash
# Test connection
docker-compose exec trading-bot python -c "import redis; r=redis.Redis(host='redis'); r.ping()"

# Check Redis logs
docker-compose logs redis
```

## Performance Tuning

### MongoDB

- Create indexes on frequently queried fields
- Use connection pooling
- Monitor slow queries

### Redis

- Set appropriate TTL for cached data
- Monitor memory usage
- Use Redis persistence (RDB/AOF)

### Trading Bot

- Adjust agent processing frequency
- Optimize LLM API calls (caching, batching)
- Monitor API rate limits

## Maintenance

### Daily Tasks

- Monitor daily reports (Slack)
- Check system health dashboard
- Review trade logs

### Weekly Tasks

- Review learning agent recommendations
- Update prompts if needed
- Check system resource usage

### Monthly Tasks

- Review performance metrics
- Optimize strategy parameters
- Update dependencies
- Review security settings

## Rollback Procedure

1. Stop current deployment:
   ```bash
   docker-compose down
   ```

2. Checkout previous version:
   ```bash
   git checkout <previous-commit>
   ```

3. Rebuild and restart:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

## Support

For issues or questions:
1. Check logs: `docker-compose logs`
2. Review documentation: `README.md`, `docs/SETUP.md`
3. Check architecture: `docs/ARCHITECTURE.md`
4. Review known issues: `docs/CURRENT_ISSUES.md`

