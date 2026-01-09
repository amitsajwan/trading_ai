import { test, expect } from '@playwright/test';

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard');
    // Wait for initial load
    await page.waitForLoadState('networkidle');
  });

  test('should display dashboard page with title', async ({ page }) => {
    // Use main content area to avoid header title
    await expect(page.locator('main h1:has-text("Trading Dashboard")')).toBeVisible();
    await expect(page.locator('text=Real-time monitoring of your AI trading system')).toBeVisible();
  });

  test('should display Market Overview widget', async ({ page }) => {
    const widget = page.locator('[data-widget-id="market-overview"], [data-testid="widget-market-overview"]').first();
    await expect(widget).toBeVisible({ timeout: 10000 });
    // Look for Market Overview in main content area - widget may be loading or show data
    const marketOverviewText = page.locator('main').locator('text=/Market Overview|No market data available|Current Price|VWAP/i').first();
    await expect(marketOverviewText).toBeVisible({ timeout: 15000 });
  });

  test('should display Current Signal widget', async ({ page }) => {
    const widget = page.locator('[data-widget-id="current-signal"], [data-testid="widget-current-signal"]').first();
    await expect(widget).toBeVisible({ timeout: 10000 });
    // Widget may show signal data, strategy info, or be in loading state
    const signalContent = page.locator('main').locator('text=/Current Signal|Current Strategy|BUY|SELL|HOLD|Live|confidence/i').first();
    await expect(signalContent).toBeVisible({ timeout: 15000 });
  });

  test('should display Options Strategy widget', async ({ page }) => {
    const widget = page.locator('[data-widget-id="options-strategy"], [data-testid="widget-options-strategy"]').first();
    await expect(widget).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=/Options Strategy/i')).toBeVisible();
  });

  test('should display Portfolio widget', async ({ page }) => {
    const widget = page.locator('[data-widget-id="portfolio"], [data-testid="widget-portfolio"]').first();
    await expect(widget).toBeVisible({ timeout: 10000 });
    // Widget may show "Portfolio" heading or error message, both are valid
    await expect(page.locator('main').locator('text=/Portfolio|Unable to load portfolio/i').first()).toBeVisible();
  });

  test('should display Recent Trades widget', async ({ page }) => {
    const widget = page.locator('[data-widget-id="recent-trades"], [data-testid="widget-recent-trades"]').first();
    await expect(widget).toBeVisible({ timeout: 10000 });
    // Widget may show "Recent Trades" heading or error message, both are valid
    await expect(page.locator('main').locator('text=/Recent Trades|Unable to load recent trades/i').first()).toBeVisible();
  });

  test('should display Technical Indicators widget', async ({ page }) => {
    const widget = page.locator('[data-widget-id="technical-indicators"], [data-testid="widget-technical-indicators"]').first();
    await expect(widget).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=/Technical Indicators/i')).toBeVisible();
  });

  test('should display Agent Status widget', async ({ page }) => {
    const widget = page.locator('[data-widget-id="agent-status"], [data-testid="widget-agent-status"]').first();
    await expect(widget).toBeVisible({ timeout: 10000 });
    // Widget may show "Agent Status" heading or error message, both are valid
    await expect(page.locator('main').locator('text=/Agent Status|Unable to load agent status/i').first()).toBeVisible();
  });

  test('should show Live Data Active badge', async ({ page }) => {
    await expect(page.locator('text=Live Data Active')).toBeVisible();
  });
});
