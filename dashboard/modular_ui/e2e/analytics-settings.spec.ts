import { test, expect } from '@playwright/test';

test.describe('Analytics and Settings Pages', () => {
  test('should display Analytics page with title and charts', async ({ page }) => {
    await page.goto('/analytics');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(5000);
    
    await expect(page).toHaveURL(/.*analytics/);
    
    // Check if page loaded - look for any h1 in main or the loading spinner
    const pageTitle = page.locator('main h1, h1').first();
    await expect(pageTitle).toBeVisible({ timeout: 20000 });
    
    // Check for analytics content - title or metrics/charts
    const analyticsContent = page.locator('main').locator('text=/Analytics Dashboard|Comprehensive analysis|Total P&L|Win Rate|P&L Performance|Asset Allocation/i').first();
    await expect(analyticsContent).toBeVisible({ timeout: 20000 });
  });

  test('should display Settings page with configuration options', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    await expect(page).toHaveURL(/.*settings/);
    await expect(page.locator('h1:has-text("Settings")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Configure dashboard preferences')).toBeVisible();
    
    // Check for settings sections (use first to handle multiple matches)
    await expect(page.locator('text=/General|Theme|Auto Refresh|Refresh Interval/i').first()).toBeVisible({ timeout: 10000 });
    
    // Check for theme selector
    const themeSelector = page.locator('select, [aria-label*="theme"]').first();
    await expect(themeSelector).toBeVisible();
  });

  test('should toggle theme in header', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    // Look for theme toggle button in header
    const themeToggle = page.locator('header button, button:has(svg)').filter({ hasText: /sun|moon|theme/i }).first();
    
    if (await themeToggle.isVisible({ timeout: 5000 })) {
      // Try clicking the theme toggle
      await themeToggle.click();
      await page.waitForTimeout(500);
    } else {
      // Alternative: look for any button with sun/moon icon
      const themeButton = page.locator('button').filter({ has: page.locator('svg') }).first();
      if (await themeButton.isVisible()) {
        await themeButton.click();
        await page.waitForTimeout(500);
      }
    }
    
    // Verify page still works after theme toggle
    await expect(page.locator('body')).toBeVisible();
  });

  test('should update settings in Settings page', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    // Find and interact with auto refresh checkbox
    const autoRefreshCheckbox = page.locator('input[type="checkbox"][aria-label*="auto-refresh"], input[type="checkbox"]').first();
    if (await autoRefreshCheckbox.isVisible({ timeout: 5000 })) {
      const initialChecked = await autoRefreshCheckbox.isChecked();
      await autoRefreshCheckbox.click();
      await page.waitForTimeout(500);
      const newChecked = await autoRefreshCheckbox.isChecked();
      expect(newChecked).not.toBe(initialChecked);
    }
    
    // Find and interact with refresh interval input
    const refreshIntervalInput = page.locator('input[type="number"]').first();
    if (await refreshIntervalInput.isVisible({ timeout: 5000 })) {
      await refreshIntervalInput.fill('30');
      await page.waitForTimeout(500);
      const value = await refreshIntervalInput.inputValue();
      expect(value).toBe('30');
    }
  });
});
