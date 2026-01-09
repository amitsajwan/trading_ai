import { test, expect } from '@playwright/test';

test.describe('Trading Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/trading');
    await page.waitForLoadState('networkidle');
    // Wait for page to be fully rendered
    await page.waitForTimeout(2000);
  });

  test('should display trading page with title', async ({ page }) => {
    await expect(page).toHaveURL(/.*trading/);
    // Use main content area to avoid header title
    await expect(page.locator('main h1:has-text("Trading")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Execute trades and manage positions')).toBeVisible();
  });

  test('should display trade execution widget', async ({ page }) => {
    // Look for trade execution form elements or buttons
    const executionWidget = page.locator('text=/Trade.*Execution|Execute.*Trade|Place.*Order|BUY|SELL/i').first();
    await expect(executionWidget).toBeVisible({ timeout: 10000 });
  });

  test('should display active signals widget', async ({ page }) => {
    const signalsWidget = page.locator('text=/Active.*Signal|Signal/i').first();
    await expect(signalsWidget).toBeVisible({ timeout: 10000 });
  });

  test('should display active positions widget', async ({ page }) => {
    const positionsWidget = page.locator('text=/Active.*Position|Position|Portfolio/i').first();
    await expect(positionsWidget).toBeVisible({ timeout: 10000 });
  });

  test('should display risk management widget', async ({ page }) => {
    const riskWidget = page.locator('text=/Risk.*Management|Risk|VaR|Drawdown/i').first();
    await expect(riskWidget).toBeVisible({ timeout: 10000 });
  });

  test('should display quick actions widget', async ({ page }) => {
    const quickActions = page.locator('text=/Quick.*Action|Action/i').first();
    await expect(quickActions).toBeVisible({ timeout: 10000 });
  });
});
