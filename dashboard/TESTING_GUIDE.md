# UI Testing Guide - Quick Start

**Purpose:** Quick reference for testing all UI components, especially Layer 8 Risk Management widgets

---

## Quick Testing Steps

### 1. Install Playwright

```bash
cd dashboard/modular_ui
npm install -D @playwright/test
npx playwright install chromium
```

### 2. Start System

```bash
# From project root
python start_local.py --provider historical --historical-from 2026-01-08 --skip-validation
```

**Wait for:** Dashboard to be available at http://localhost:8888 (check logs)

### 3. Run Tests

```bash
cd dashboard/tests/playwright
npx playwright test
```

---

## Manual Testing Checklist

### ✅ Core Trading Widgets

1. **Market Overview Widget**
   - [ ] Current price displays
   - [ ] Price change shows (green/red)
   - [ ] Volume and VWAP visible

2. **Current Signal Widget**
   - [ ] Latest signal displays
   - [ ] BUY/SELL/HOLD action visible
   - [ ] Confidence score shown

3. **Portfolio Widget**
   - [ ] Active positions listed
   - [ ] P&L shows (green/red)
   - [ ] Kelly calculator works

4. **Recent Trades Widget**
   - [ ] Trade history displays
   - [ ] P&L per trade visible

5. **Technical Indicators Widget**
   - [ ] RSI, MACD, ADX shown
   - [ ] Bollinger Bands visible

6. **Agent Status Widget**
   - [ ] All 15 agents listed
   - [ ] Status per agent shown

### ✅ Layer 8 Risk Widgets

7. **Portfolio Heat Widget** ⭐
   - [ ] Widget visible on dashboard
   - [ ] Heat utilization bar displays
   - [ ] Percentage shown (e.g., "45.2%")
   - [ ] Color coding works:
     - Green: < 50% heat
     - Yellow: 50-80% heat
     - Red: > 80% heat
   - [ ] Daily P&L displays
   - [ ] Active positions count shows
   - [ ] Account balance visible
   - [ ] Risk status indicator:
     - "Risk Limits Within Bounds" (green)
     - "High Heat - Consider Reducing Positions" (yellow)
     - "Trading Restricted - Risk Limits Exceeded" (red)

8. **Kelly Sizing Widget** ⭐
   - [ ] Widget visible on dashboard
   - [ ] Manual mode toggle works
   - [ ] Win probability slider (0.1 - 0.9)
   - [ ] Risk/Reward ratio slider (0.5 - 5.0)
   - [ ] "Calculate Kelly Size" button
   - [ ] Kelly percentage displays after calculation
   - [ ] Recommended position size shown
   - [ ] Risk amount calculated
   - [ ] Historical stats display (if available)
   - [ ] Warning shows for high Kelly (> 30%)

9. **Approval History Widget** ⭐
   - [ ] Widget visible on dashboard
   - [ ] Approval history list displays
   - [ ] Decision icons show:
     - ✅ Green checkmark (approved)
     - ❌ Red X (rejected)
     - ⚠️ Yellow alert (reduced)
   - [ ] Decision details show:
     - Decision type (APPROVED/REJECTED/REDUCED)
     - Reason
     - Approved quantity
     - Kelly percentage
     - Risk amount
     - Timestamp
   - [ ] Approval statistics display:
     - Total reviews
     - Approval rate %
     - Rejection rate %
     - Reduction rate %

10. **Risk Management Widget** ⭐
    - [ ] Widget visible on dashboard
    - [ ] Portfolio heat section displays (Layer 8 integration)
    - [ ] Approval statistics show
    - [ ] Risk settings form:
      - Max Position Size input
      - Max Daily Loss input
      - Stop Loss % input
      - Take Profit % input
    - [ ] Toggles work:
      - "Enable Auto Stop Loss" checkbox
      - "Enable Auto Take Profit" checkbox
    - [ ] "Save Settings" button
    - [ ] Settings save to localStorage
    - [ ] "Saved" confirmation shows

---

## Automated Playwright Tests

### Run All Tests

```bash
cd dashboard/tests/playwright
npx playwright test
```

### Run Specific Test

```bash
# Portfolio Heat Widget
npx playwright test tests/widgets/portfolio-heat.spec.ts

# Kelly Sizing Widget
npx playwright test tests/widgets/kelly-sizing.spec.ts

# Approval History Widget
npx playwright test tests/widgets/approval-history.spec.ts

# Risk Management Widget
npx playwright test tests/widgets/risk-management.spec.ts

# Dashboard Page
npx playwright test tests/dashboard.spec.ts

# Risk API
npx playwright test tests/api/risk-api.spec.ts
```

### Run in UI Mode (Interactive)

```bash
npx playwright test --ui
```

### Run in Headed Mode (See Browser)

```bash
npx playwright test --headed
```

---

## API Testing (Manual)

### Test Risk API Endpoints

```bash
# Portfolio Heat Summary
curl http://localhost:8888/api/risk/portfolio/summary

# Heat Utilization
curl http://localhost:8888/api/risk/portfolio/heat-utilization

# Calculate Kelly
curl -X POST http://localhost:8888/api/risk/kelly/calculate \
  -H "Content-Type: application/json" \
  -d '{"account_balance": 100000, "max_loss_per_unit": 100, "win_probability": 0.55, "risk_reward_ratio": 2.0}'

# Approval History
curl http://localhost:8888/api/risk/approval/history?limit=10

# Approval Statistics
curl http://localhost:8888/api/risk/approval/stats

# Can Open Position
curl -X POST http://localhost:8888/api/risk/portfolio/can-open-position?proposed_max_loss=1000
```

---

## Expected Results

### Portfolio Heat Widget
- **Heat Bar:** Should show percentage utilization
- **Colors:** Green (< 50%), Yellow (50-80%), Red (> 80%)
- **Metrics:** Daily P&L, positions count, account balance

### Kelly Sizing Widget
- **Manual Mode:** Sliders for win prob and R:R
- **Calculation:** Kelly % between 0-1
- **Warnings:** Shows warning if Kelly > 30%

### Approval History Widget
- **History:** List of recent decisions
- **Icons:** Correct icons for each decision type
- **Stats:** Approval/rejection/reduction rates

### Risk Management Widget
- **Heat Section:** Shows portfolio heat (Layer 8)
- **Stats:** Approval statistics
- **Form:** All inputs editable and saveable

---

## Troubleshooting

### Widgets Not Displaying

1. **Check System Status:**
   ```bash
   curl http://localhost:8888/api/health
   curl http://localhost:8888/api/risk/portfolio/summary
   ```

2. **Check Browser Console:**
   - Open DevTools (F12)
   - Look for errors in Console tab
   - Check Network tab for failed API calls

3. **Check Test IDs:**
   - Widgets should have `data-testid` attributes
   - Verify in browser DevTools (Elements tab)

### API Errors

1. **Check Services Running:**
   ```bash
   # Check if services are up
   netstat -an | findstr "8004 8005 8006 8007 8888"
   ```

2. **Check API Logs:**
   - Look at terminal output from `start_local.py`
   - Check for error messages

3. **Verify Credentials:**
   - Check `local.env` has valid credentials
   - Check API endpoints return data

---

## Test Coverage Summary

### ✅ Manual Testing
- [x] All widgets visible
- [x] All widgets functional
- [x] API endpoints working
- [x] Layer 8 features integrated

### ✅ Automated Testing (Playwright)
- [x] Dashboard page tests
- [x] Portfolio Heat Widget tests
- [x] Kelly Sizing Widget tests
- [x] Approval History Widget tests
- [x] Risk Management Widget tests
- [x] Risk API endpoint tests

### 📊 Test Statistics
- **Total Test Files:** 6
- **Widget Tests:** 4
- **Page Tests:** 1
- **API Tests:** 1
- **Total Test Cases:** 50+

---

**Ready to Test!** 🧪

Follow the checklist above to verify all UI components are working correctly.
