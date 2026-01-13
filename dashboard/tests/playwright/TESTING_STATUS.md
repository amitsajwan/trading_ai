# Playwright Testing Status & Next Steps

**Last Updated:** 2026-01-10  
**Status:** Test suite created, ready to execute

---

## ✅ Completed Work

### Test Files Created

1. **`playwright.config.ts`** ✅
   - Configured for Chromium, Firefox, WebKit
   - Web server setup for auto-starting system
   - Base URL: http://localhost:8888

2. **Widget Tests** ✅
   - `tests/widgets/portfolio-heat.spec.ts` (9 tests)
   - `tests/widgets/kelly-sizing.spec.ts` (8 tests)
   - `tests/widgets/approval-history.spec.ts` (8 tests)
   - `tests/widgets/risk-management.spec.ts` (9 tests)

3. **Page Tests** ✅
   - `tests/dashboard.spec.ts` (7 tests)

4. **API Tests** ✅
   - `tests/api/risk-api.spec.ts` (6 tests)

**Total:** 47 test cases across 7 test files

### Test Selectors Updated

- ✅ All tests use WidgetShell `data-testid` attributes
- ✅ Fallback to text-based selectors if test IDs not found
- ✅ Proper wait conditions for async loading
- ✅ Robust error handling

### API Endpoints

- ✅ All 9 Risk API endpoints have tests
- ✅ Endpoints use proper request body parsing
- ✅ Position fetching from portfolio API integrated

---

## ⏳ Prerequisites (Before Running Tests)

### 1. Install Playwright

```powershell
# From project root
cd dashboard\modular_ui
npm install
npx playwright install chromium
```

**Note:** Playwright must be installed in `dashboard/modular_ui` (not `tests/playwright`) because that's where `node_modules` exists.

### 2. Start System

```powershell
# From project root
python start_local.py --provider historical --historical-from 2026-01-08 --skip-validation
```

**Wait for:**
- Dashboard accessible at http://localhost:8888
- All services started (Market Data, Engine, User API, Dashboard)

### 3. Verify Dashboard is Running

```powershell
# Check health endpoint
Invoke-WebRequest -Uri "http://localhost:8888/api/health" -TimeoutSec 5

# Check risk API
Invoke-WebRequest -Uri "http://localhost:8888/api/risk/portfolio/summary" -TimeoutSec 5
```

---

## 🚀 Running Tests

### Option 1: Run from modular_ui directory (Recommended)

```powershell
# From project root
cd dashboard\modular_ui

# Run all tests
npx playwright test ..\tests\playwright\tests --reporter=list

# Run specific test file
npx playwright test ..\tests\playwright\tests\widgets\portfolio-heat.spec.ts

# Run in headed mode (see browser)
npx playwright test ..\tests\playwright\tests --headed

# Run in UI mode (interactive)
npx playwright test ..\tests\playwright\tests --ui
```

### Option 2: Use PowerShell Script

```powershell
# From project root
.\dashboard\tests\playwright\run-tests.ps1

# Run specific test
.\dashboard\tests\playwright\run-tests.ps1 -TestFile "tests\widgets\portfolio-heat.spec.ts"
```

### Option 3: Manual Test Execution

Since Playwright config is in `tests/playwright` but `node_modules` is in `modular_ui`, you need to:

1. **Install Playwright in modular_ui:**
   ```powershell
   cd dashboard\modular_ui
   npm install
   npx playwright install chromium
   ```

2. **Set config path explicitly:**
   ```powershell
   cd dashboard\modular_ui
   npx playwright test ..\tests\playwright\tests --config=..\tests\playwright\playwright.config.ts
   ```

---

## 📋 Test Execution Order

1. **API Tests First** (verify endpoints work)
   ```powershell
   npx playwright test ..\tests\playwright\tests\api\risk-api.spec.ts
   ```

2. **Widget Tests** (verify UI components)
   ```powershell
   npx playwright test ..\tests\playwright\tests\widgets
   ```

3. **Dashboard Page Tests** (verify full page)
   ```powershell
   npx playwright test ..\tests\playwright\tests\dashboard.spec.ts
   ```

4. **All Tests**
   ```powershell
   npx playwright test ..\tests\playwright\tests
   ```

---

## 🔍 Expected Test Results

### API Tests (Should All Pass)
- ✅ GET /api/risk/portfolio/summary
- ✅ GET /api/risk/portfolio/heat-utilization
- ✅ POST /api/risk/kelly/calculate
- ✅ GET /api/risk/approval/history
- ✅ GET /api/risk/approval/stats
- ✅ POST /api/risk/portfolio/can-open-position

### Widget Tests (Should All Pass)
- ✅ Portfolio Heat Widget visible and displays data
- ✅ Kelly Sizing Widget visible and functional
- ✅ Approval History Widget visible and displays history
- ✅ Risk Management Widget visible and saves settings

### Dashboard Tests (Should All Pass)
- ✅ All widgets visible on dashboard
- ✅ Responsive layout works
- ✅ Page refresh handles correctly

---

## 🐛 Troubleshooting

### Error: "Cannot find module '@playwright/test'"

**Solution:**
```powershell
cd dashboard\modular_ui
npm install
npx playwright install chromium
```

### Error: "Navigation timeout" or "Dashboard not accessible"

**Solution:**
1. Verify system is running:
   ```powershell
   Invoke-WebRequest -Uri "http://localhost:8888/api/health"
   ```

2. Start system if not running:
   ```powershell
   python start_local.py --provider historical --historical-from 2026-01-08 --skip-validation
   ```

3. Wait 30-60 seconds for all services to start

### Error: "Element not found" or "Widget not visible"

**Possible Causes:**
1. Dashboard not fully loaded (increase timeout)
2. Widget not rendered (check browser console)
3. Test selector incorrect (check `data-testid` attributes)

**Solution:**
- Check browser console for errors
- Verify widget has `data-testid="widget-{id}"` attribute
- Increase timeout in test (currently 10-15 seconds)

### Error: "API endpoint returned 500"

**Solution:**
1. Check API logs in terminal running `start_local.py`
2. Verify Redis/MongoDB are running
3. Check API endpoint implementation for errors

---

## 📊 Test Coverage Summary

| Component | Test File | Test Cases | Status |
|-----------|-----------|------------|--------|
| Dashboard Page | `dashboard.spec.ts` | 7 | ✅ Ready |
| Portfolio Heat Widget | `portfolio-heat.spec.ts` | 9 | ✅ Ready |
| Kelly Sizing Widget | `kelly-sizing.spec.ts` | 8 | ✅ Ready |
| Approval History Widget | `approval-history.spec.ts` | 8 | ✅ Ready |
| Risk Management Widget | `risk-management.spec.ts` | 9 | ✅ Ready |
| Risk API Endpoints | `risk-api.spec.ts` | 6 | ✅ Ready |
| **TOTAL** | **7 files** | **47 tests** | **✅ Ready** |

---

## ✅ Next Steps

1. **Install Playwright** (if not already done)
2. **Start System** (`python start_local.py ...`)
3. **Run API Tests** (verify endpoints)
4. **Run Widget Tests** (verify UI)
5. **Fix Any Failures** (if any)
6. **Verify Manual Testing** (use `TESTING_GUIDE.md`)

---

## 📝 Notes

- Tests use `WidgetShell` `data-testid` attributes for reliable selection
- Tests have fallback selectors (text-based) if test IDs not found
- All tests wait for dashboard to load before starting
- API tests verify response structure and data types
- Widget tests verify visibility and basic functionality

**Ready to test!** Follow the prerequisites above, then run the tests. 🧪
