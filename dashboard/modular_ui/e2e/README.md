# UI Component Testing with Playwright

This directory contains end-to-end tests for verifying all UI components are working correctly.

## Prerequisites

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Install Playwright browsers:**
   ```bash
   npx playwright install chromium
   ```

3. **Ensure backend services are running:**
   - Dashboard server (port 8888)
   - Market Data API (port 8004)
   - Engine API (port 8006)
   - User API (port 8007)
   - Redis WebSocket Gateway (port 8889) - optional for WebSocket tests

## Running Tests

### Run all tests:
```bash
npm run test:e2e
```

### Run tests in UI mode (interactive):
```bash
npm run test:e2e:ui
```

### Run tests in headed mode (see browser):
```bash
npm run test:e2e:headed
```

### Run specific test file:
```bash
npx playwright test e2e/dashboard.spec.ts
```

### Run tests with debug:
```bash
npx playwright test --debug
```

## Test Coverage

### Dashboard Page (`dashboard.spec.ts`)
- ✅ Market Overview widget
- ✅ Current Signal widget
- ✅ Options Strategy widget
- ✅ Portfolio widget
- ✅ Recent Trades widget
- ✅ Technical Indicators widget
- ✅ Agent Status widget

### Market Data Page (`market-data.spec.ts`)
- ✅ Live Tick Data widget
- ✅ Options Chain widget
- ✅ Order Flow widget
- ✅ Historical Data widget
- ✅ Instrument selector

### Trading Page (`trading.spec.ts`)
- ✅ Trade Execution widget
- ✅ Active Signals widget
- ✅ Active Positions widget
- ✅ Risk Management widget
- ✅ Quick Actions widget

### Navigation (`navigation.spec.ts`)
- ✅ Header component
- ✅ Sidebar navigation
- ✅ Navigation between pages
- ✅ 404 handling

### Analytics & Settings (`analytics-settings.spec.ts`)
- ✅ Analytics page with charts and metrics
- ✅ Settings page configuration
- ✅ Theme toggle functionality

### API Integration (`api-integration.spec.ts`)
- ✅ Health endpoints
- ✅ Market data endpoints
- ✅ Trading endpoints
- ✅ Portfolio endpoints

### WebSocket (`websocket.spec.ts`)
- ✅ WebSocket connection attempt
- ✅ Graceful disconnection handling

## Troubleshooting

### Tests fail with connection errors:
- Ensure all backend services are running
- Check that ports 8888, 8004, 8006, 8007 are available
- Verify Redis is running (port 6379)

### Tests timeout:
- Increase timeout in `playwright.config.ts`
- Check network connectivity to backend services
- Verify backend APIs are responding at `/api/health`

### WebSocket tests fail:
- WebSocket gateway (port 8889) is optional
- Tests will pass if WebSocket is unavailable (graceful degradation)

## CI/CD Integration

Tests can be run in CI/CD pipelines:
```bash
npx playwright test --reporter=html
```

HTML report will be generated in `playwright-report/` directory.
