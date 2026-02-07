# DASHBOARD - Trading System Web Interface

**Status: ✅ PRODUCTION READY** - Complete FastAPI-based trading dashboard with real-time updates and professional UI.

A comprehensive web dashboard providing complete control over the automated trading system with real-time monitoring, manual overrides, and performance analytics.

**📚 Documentation:** See [docs/index.md](docs/index.md) for complete documentation index.

## 🎯 Purpose & Architecture

The dashboard provides the primary user interface for the trading system:

```
Web UI → FastAPI Backend → UI Shell → Trading Engine → Market Data & Execution
```

### **Core Components:**
- **FastAPI Application**: RESTful API backend with WebSocket support
- **Real-time Updates**: Live data streaming via WebSocket gateway
- **Trading Cockpit**: Manual trade execution and system control
- **Performance Analytics**: P&L tracking and system metrics
- **Risk Management**: Portfolio monitoring and emergency controls

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js (for frontend development)
- Redis & MongoDB (running)
- Trading system modules

### Installation
```bash
# Install Python dependencies
pip install -r requirements.txt

# For frontend development
cd ui && npm install
```

### Basic Usage
```bash
# Start dashboard server
python dashboard_pro.py

# Access at http://localhost:8888
```

## 🆕 Recent Updates (January 2026)

### ✅ Data Architecture Completion
- **Hybrid Data Services**: Complete HTTP/WebSocket/hybrid data architecture with seamless switching
- **Real-time WebSocket Integration**: Redis pub/sub to WebSocket gateway with ACL and rate limiting
- **Data Caching Layer**: Prevents UI flickering during data source transitions
- **State Management**: Comprehensive Redux store with domain slices

### ✅ Documentation Overhaul
- **DATA_REFERENCE.md**: Complete API specifications, WebSocket channels, and data schemas
- **Documentation Index**: Organized docs structure in [docs/index.md](docs/index.md)
- **Integration Examples**: React components, API clients, and WebSocket usage patterns
- **Performance Specifications**: Latency targets, throughput limits, and error handling

### ✅ Testing Infrastructure
- **Automated Test Suite**: 38 passing tests covering data services, WebSocket routing, and caching
- **E2E Testing**: Playwright tests for critical user journeys and component interactions
- **Performance Monitoring**: Data freshness validation and error boundary testing

### ✅ Feature Completeness
- **Real-time Widgets**: Live tick data, signals, agent analysis, and portfolio updates
- **Trading Controls**: Manual execution, signal approval, and risk management
- **Analytics Dashboard**: Performance metrics, trade history, and risk visualization
- **Administrative Tools**: System health monitoring and configuration management

## 🔧 API Reference

### Factory Functions
```python
from dashboard.api import (
    build_dashboard_app,     # Main FastAPI app factory
    create_websocket_manager, # WebSocket connection manager
    get_dashboard_routes     # Route configuration
)
```

### Key Endpoints
```python
# System Status
GET  /api/system-health       # System health check
GET  /api/system-status       # Complete system status

# Trading Operations
GET  /api/latest-decision     # Latest trading decision
POST /api/execute-signal      # Execute trading signal
GET  /api/portfolio           # Portfolio summary

# Market Data
GET  /api/market-data         # Market data overview
GET  /api/technical-indicators # Technical indicators

# WebSocket
WS   /ws                      # Real-time updates stream
```

### WebSocket Events
- `market_update` - Real-time market data
- `signal_update` - New trading signals
- `decision_update` - Trading decisions
- `portfolio_update` - Portfolio changes

## 🧪 Testing

### Run Tests
```bash
# From dashboard directory
cd dashboard
pytest tests/

# Run API tests
pytest tests/test_smoke.py

# Run UI component tests
pytest tests/test_components.py

# With coverage
pytest --cov=src --cov-report=html
```

### Test Structure
- `tests/test_smoke.py` - API smoke tests
- `tests/test_components.py` - UI component tests
- `tests/test_websocket.py` - WebSocket integration tests

## 🏗️ Development

### Project Structure
```
dashboard/
├── app.py                   # Main FastAPI application
├── dashboard_pro.py         # Production startup script
├── ui/                      # Frontend components
│   ├── components/          # React components
│   ├── pages/              # Dashboard pages
│   └── utils/              # Frontend utilities
├── tests/                   # Test suite
│   ├── test_smoke.py       # API tests
│   ├── test_components.py  # UI tests
│   └── conftest.py         # Test configuration
├── static/                  # Static assets
├── templates/              # HTML templates
└── README.md              # This file
```

### Adding New Features
1. Define API endpoints in `app.py`
2. Add frontend components in `ui/components/`
3. Add tests in `tests/`
4. Update this README

## 📊 Dependencies

### Internal Dependencies
- `ui_shell` - UI abstraction layer
- `engine_module` - Trading decisions
- `user_module` - User accounts
- `market_data` - Market data access

### External Dependencies
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `websockets` - WebSocket support
- `jinja2` - Template engine

## 🔍 Troubleshooting

### Common Issues
- **Port conflicts**: Check if port 8888 is available
- **WebSocket connection failed**: Verify Redis WebSocket gateway
- **UI not loading**: Check static file serving configuration

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python dashboard_pro.py
```

## 🤝 Contributing

1. Follow the existing code style
2. Add tests for new features
3. Update API documentation
4. Submit PR with clear description
