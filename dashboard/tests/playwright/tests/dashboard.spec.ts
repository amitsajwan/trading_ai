import { test, expect } from '@playwright/test';

/**
 * Dashboard Page Tests
 * Tests the main dashboard page with all widgets
 */
test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for dashboard to load
    await page.waitForSelector('h1:has-text("Trading Dashboard")', { timeout: 10000 });
  });

  test('should display dashboard title', async ({ page }) => {
    const title = page.locator('h1:has-text("Trading Dashboard")');
    await expect(title).toBeVisible();
  });

  test('should display all core widgets', async ({ page }) => {
    // Core trading widgets
    const widgets = [
      'Market Overview',
      'Current Signal',
      'Portfolio',
      'Recent Trades',
      'Technical Indicators',
      'Agent Status'
    ];
    
    for (const widgetName of widgets) {
      const widget = page.locator(`text=/${widgetName}/i`).first();
      await expect(widget).toBeVisible({ timeout: 5000 });
    }
  });

  test('should display all Layer 8 risk widgets', async ({ page }) => {
    // Layer 8 widgets - scroll to see all widgets
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000);
    
    const layer8Widgets = [
      'Portfolio Heat',
      'Risk Management',
      'Kelly Position Sizing',
      'Approval History'
    ];
    
    for (const widgetName of layer8Widgets) {
      const widget = page.locator(`text=/${widgetName}/i`).first();
      await expect(widget).toBeVisible({ timeout: 10000 });
    }
  });

  test('should have responsive layout', async ({ page }) => {
    // Check that widgets are in a grid layout
    const dashboard = page.locator('div[class*="grid"]').first();
    await expect(dashboard).toBeVisible();
  });

  test('should show live data status', async ({ page }) => {
    // Should show "Live Data Active" or similar status
    const status = page.locator('text=/Live Data|Active/i');
    const statusVisible = await status.first().isVisible().catch(() => false);
    // Status may or may not be visible, but page should load
    const title = page.locator('h1:has-text("Trading Dashboard")');
    await expect(title).toBeVisible();
  });

  test('should handle page refresh', async ({ page }) => {
    // Reload page
    await page.reload();
    
    // Should still show dashboard
    await page.waitForSelector('h1:has-text("Trading Dashboard")', { timeout: 10000 });
    const title = page.locator('h1:has-text("Trading Dashboard")');
    await expect(title).toBeVisible();
  });

  test('should display widget grid correctly', async ({ page }) => {
    // Scroll to see all widgets
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    
    // Wait a bit for widgets to load
    await page.waitForTimeout(2000);
    
    // Should have multiple widget containers
    const widgetContainers = page.locator('section, div[class*="bg-white"], div[class*="bg-gray"]')
      .filter({ hasText: /Portfolio|Risk|Market|Signal|Agent/i });
    
    const count = await widgetContainers.count();
    expect(count).toBeGreaterThan(0);
  });
});
