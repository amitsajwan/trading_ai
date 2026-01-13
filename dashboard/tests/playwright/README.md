# Playwright UI Testing Suite

Comprehensive end-to-end tests for the Trading Dashboard UI, including all Layer 8 Risk Management widgets.

## Setup

### Install Dependencies

```bash
cd dashboard
npm install -D @playwright/test
npx playwright install
```

### Install Browser Binaries

```bash
npx playwright install chromium firefox webkit
```

## Running Tests

### Run All Tests

```bash
cd dashboard/tests/playwright
npx playwright test
```

### Run Specific Test File

```bash
# Portfolio Heat Widget tests
npx playwright test tests/widgets/portfolio-heat.spec.ts

# Kelly Sizing Widget tests
npx playwright test tests/widgets/kelly-sizing.spec.ts

# Approval History Widget tests
npx playwright test tests/widgets/approval-history.spec.ts

# Risk Management Widget tests
npx playwright test tests/widgets/risk-management.spec.ts

# Dashboard page tests
npx playwright test tests/dashboard.spec.ts

# Risk API tests
npx playwright test tests/api/risk-api.spec.ts
```

### Run in Headed Mode (See Browser)

```bash
npx playwright test --headed
```

### Run in UI Mode (Interactive)

```bash
npx playwright test --ui
```

### Run with Specific Browser

```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

## Test Structure

```
dashboard/tests/playwright/
├── tests/
│   ├── dashboard.spec.ts              # Main dashboard page
│   ├── widgets/
│   │   ├── portfolio-heat.spec.ts     # Portfolio Heat Widget (Layer 8)
│   │   ├── kelly-sizing.spec.ts       # Kelly Sizing Widget (Layer 8)
│   │   ├── approval-history.spec.ts   # Approval History Widget (Layer 8)
│   │   └── risk-management.spec.ts    # Risk Management Widget (Layer 8)
│   └── api/
│       └── risk-api.spec.ts           # Risk API endpoints (Layer 8)
├── playwright.config.ts               # Playwright configuration
└── README.md                          # This file
```

## Test Coverage

### ✅ Dashboard Page
- Dashboard title display
- All core widgets visible
- All Layer 8 widgets visible
- Responsive layout
- Page refresh handling

### ✅ Portfolio Heat Widget (Layer 8)
- Widget display
- Heat utilization bar
- Heat percentage display
- Daily P&L display
- Active positions count
- Color-coded risk levels
- Account balance display
- Risk status indicators

### ✅ Kelly Sizing Widget (Layer 8)
- Widget display
- Manual mode toggle
- Manual inputs (win prob, R:R)
- Calculate button
- Kelly percentage display
- Position size recommendations
- Risk indicators
- Error handling

### ✅ Approval History Widget (Layer 8)
- Widget display
- Approval history list
- Decision icons
- Approval statistics
- Empty state handling
- Loading state handling

### ✅ Risk Management Widget (Layer 8)
- Widget display
- Portfolio heat section
- Approval statistics
- Risk settings form
- Settings editing
- Save functionality
- Stop loss/take profit inputs
- Auto stop loss toggle

### ✅ Risk API Endpoints (Layer 8)
- GET /api/risk/portfolio/summary
- GET /api/risk/portfolio/heat-utilization
- POST /api/risk/kelly/calculate
- GET /api/risk/approval/history
- GET /api/risk/approval/stats
- POST /api/risk/portfolio/can-open-position

## Prerequisites

Before running tests, ensure:

1. **System is running:**
   ```bash
   python start_local.py --skip-validation
   ```

2. **Dashboard is accessible:**
   - URL: http://localhost:8888
   - All services started (Market Data, Engine, User API, Dashboard)

3. **Redis and MongoDB running:**
   ```bash
   docker-compose -f docker-compose.data.yml up -d
   ```

## Test Execution Order

1. **Start System** (manual or via webServer in config)
2. **Run API Tests** (verify endpoints work)
3. **Run Widget Tests** (verify UI components)
4. **Run Dashboard Tests** (verify full page)

## Debugging

### View Test Execution

```bash
npx playwright test --headed --debug
```

### View Trace

```bash
# Run with trace
npx playwright test --trace on

# Open trace viewer
npx playwright show-trace trace.zip
```

### Screenshots on Failure

Screenshots are automatically saved on test failure in `test-results/` directory.

## Continuous Integration

Tests can be run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Install Playwright
  run: npx playwright install --with-deps

- name: Run Playwright tests
  run: npx playwright test
```

## Writing New Tests

### Example Test Structure

```typescript
import { test, expect } from '@playwright/test';

test.describe('My Widget', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="my-widget"]');
  });

  test('should display widget', async ({ page }) => {
    const widget = page.locator('[data-testid="my-widget"]');
    await expect(widget).toBeVisible();
  });
});
```

### Best Practices

1. **Use data-testid attributes** for reliable element selection
2. **Wait for elements** before assertions
3. **Test user interactions** (clicks, inputs, toggles)
4. **Test error states** and loading states
5. **Test API integration** separately from UI

## Troubleshooting

### Tests Fail: "Navigation timeout"

**Issue:** Dashboard not starting  
**Solution:** Ensure `start_local.py` is running and accessible at http://localhost:8888

### Tests Fail: "Element not found"

**Issue:** Widget not rendering  
**Solution:** 
- Check browser console for errors
- Verify widget has `data-testid` attribute
- Increase timeout in `waitForSelector`

### API Tests Fail: "Request failed"

**Issue:** API endpoints not responding  
**Solution:** 
- Verify services are running (ports 8004, 8005, 8006, 8007, 8888)
- Check API logs for errors
- Verify credentials are set correctly

## Maintenance

- Update tests when UI components change
- Add tests for new widgets/features
- Keep test selectors up-to-date
- Review and update test data as needed

---

**Happy Testing!** 🧪
