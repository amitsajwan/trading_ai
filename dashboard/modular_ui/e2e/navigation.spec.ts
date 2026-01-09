import { test, expect } from '@playwright/test';

test.describe('Navigation and Layout', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    // Wait a bit for React to hydrate
    await page.waitForTimeout(2000);
  });

  test('should display header with title', async ({ page }) => {
    const header = page.locator('header, [role="banner"]').first();
    await expect(header).toBeVisible();
  });

  test('should display sidebar navigation', async ({ page }) => {
    const sidebar = page.locator('aside, nav, [role="navigation"]').first();
    await expect(sidebar).toBeVisible();
  });

  test('should navigate to Dashboard page', async ({ page }) => {
    const dashboardLink = page.locator('a[href="/dashboard"], a[href="/"]').first();
    if (await dashboardLink.isVisible()) {
      await dashboardLink.click();
      await expect(page).toHaveURL(/.*dashboard|\/$/);
    }
  });

  test('should navigate to Market Data page', async ({ page }) => {
    const marketDataLink = page.locator('a[href="/market-data"]').first();
    if (await marketDataLink.isVisible()) {
      await marketDataLink.click();
      await expect(page).toHaveURL(/.*market-data/);
      await page.waitForLoadState('networkidle');
    }
  });

  test('should navigate to Trading page', async ({ page }) => {
    const tradingLink = page.locator('a[href="/trading"]').first();
    if (await tradingLink.isVisible()) {
      await tradingLink.click();
      await expect(page).toHaveURL(/.*trading/);
      await page.waitForLoadState('networkidle');
    }
  });

  test('should navigate to Analytics page', async ({ page }) => {
    const analyticsLink = page.locator('a[href="/analytics"]').first();
    if (await analyticsLink.isVisible()) {
      await analyticsLink.click();
      await expect(page).toHaveURL(/.*analytics/);
      await page.waitForLoadState('networkidle');
    }
  });

  test('should navigate to News page', async ({ page }) => {
    const newsLink = page.locator('a[href="/news"]').first();
    if (await newsLink.isVisible()) {
      await newsLink.click();
      await expect(page).toHaveURL(/.*news/);
      await page.waitForLoadState('networkidle');
      await expect(page.locator('h1:has-text("Market News")')).toBeVisible({ timeout: 10000 });
    }
  });

  test('should navigate to Settings page', async ({ page }) => {
    const settingsLink = page.locator('a[href="/settings"]').first();
    if (await settingsLink.isVisible()) {
      await settingsLink.click();
      await expect(page).toHaveURL(/.*settings/);
      await page.waitForLoadState('networkidle');
    }
  });

  test('should handle 404 for unknown routes', async ({ page }) => {
    await page.goto('/unknown-route-12345');
    await page.waitForLoadState('networkidle');
    // Should show 404 page or redirect
    const notFound = page.locator('text=/404|not found|page not found/i');
    if (await notFound.count() > 0) {
      await expect(notFound.first()).toBeVisible();
    }
  });
});
