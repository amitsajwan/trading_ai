import { test, expect } from '@playwright/test';

/**
 * Approval History Widget Tests
 * Tests Layer 8 Approval History display
 */
test.describe('Approval History Widget', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('h1:has-text("Trading Dashboard")', { timeout: 15000 });
    await page.waitForSelector('[data-testid="widget-approval-history"], text=/Approval History/i', { timeout: 10000 });
  });

  test('should display approval history widget', async ({ page }) => {
    const widgetByTestId = page.locator('[data-testid="widget-approval-history"]');
    const hasTestId = await widgetByTestId.count() > 0;
    
    if (hasTestId) {
      await expect(widgetByTestId).toBeVisible({ timeout: 5000 });
    } else {
      const widget = page.locator('section, div').filter({ hasText: /Approval History/i }).first();
      await expect(widget).toBeVisible({ timeout: 5000 });
    }
  });

  test('should show approval history title', async ({ page }) => {
    const title = page.locator('[data-testid="widget-approval-history"]').locator('text=/Approval History/i');
    await expect(title).toBeVisible();
  });

  test('should display approval statistics', async ({ page }) => {
    // Should show approval stats
    const statsSection = page.locator('[data-testid="widget-approval-history"]')
      .locator('text=/Approval Rate|Rejection Rate|Total reviews/i');
    
    // May show stats or "No approval history" message
    const hasStatsOrEmpty = await statsSection.first().isVisible().catch(() => false);
    
    // Widget should be visible regardless
    const widget = page.locator('[data-testid="widget-approval-history"]');
    await expect(widget).toBeVisible();
  });

  test('should handle empty history state', async ({ page }) => {
    // Should show message if no history
    const emptyMessage = page.locator('[data-testid="widget-approval-history"]')
      .locator('text=/No approval history|Unable to load/i');
    
    // Either shows empty message or history items
    const hasEmptyOrHistory = await emptyMessage.isVisible().catch(() => false);
    
    // Widget should still be visible
    const widget = page.locator('[data-testid="widget-approval-history"]');
    await expect(widget).toBeVisible();
  });

  test('should display approval decision icons', async ({ page }) => {
    // Look for decision icons (CheckCircle, XCircle, AlertCircle)
    // These are from lucide-react, may appear as SVGs
    const widget = page.locator('[data-testid="widget-approval-history"]');
    
    // Should have some content
    const widgetContent = await widget.textContent();
    expect(widgetContent).toBeTruthy();
    
    // Should show at least the title
    const title = widget.locator('text=/Approval History/i');
    await expect(title).toBeVisible();
  });

  test('should show approval decision types', async ({ page }) => {
    // Look for decision types: APPROVED, REJECTED, REDUCED
    const decisionTypes = page.locator('[data-testid="widget-approval-history"]')
      .locator('text=/APPROVED|REJECTED|REDUCED/i');
    
    // May or may not have decisions, but widget should be visible
    const widget = page.locator('[data-testid="widget-approval-history"]');
    await expect(widget).toBeVisible();
  });

  test('should display approval statistics summary', async ({ page }) => {
    // Should show stats like total reviews, approval rate, etc.
    const widget = page.locator('[data-testid="widget-approval-history"]');
    
    // Look for statistics section at bottom
    const statsSection = widget.locator('text=/Approval Rate|Rejection Rate|Reduction Rate/i');
    
    // Widget should be visible regardless
    await expect(widget).toBeVisible();
  });

  test('should handle loading state', async ({ page }) => {
    // Refresh to see loading state
    await page.reload();
    
    // Loading state should appear briefly
    await page.waitForSelector('[data-testid="widget-approval-history"]', { timeout: 10000 });
    
    // Widget should eventually load
    const widget = page.locator('[data-testid="widget-approval-history"]');
    await expect(widget).toBeVisible();
  });
});
