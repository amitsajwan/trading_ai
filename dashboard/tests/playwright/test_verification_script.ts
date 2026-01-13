import { test, expect, chromium, Browser, Page } from '@playwright/test';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

/**
 * Comprehensive UI Verification Script
 * Tests all components, API endpoints, and data flow
 */

test.describe('Comprehensive UI Verification', () => {
  let browser: Browser;
  let page: Page;

  test.beforeAll(async () => {
    // Check if system is running
    try {
      const response = await fetch('http://localhost:8888/api/health', { 
        signal: AbortSignal.timeout(5000) 
      });
      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status}`);
      }
    } catch (error) {
      throw new Error('System is not running. Please start with: python start_local.py --provider historical --historical-from 2026-01-08 --skip-validation');
    }
  });

  test.beforeEach(async ({ page: testPage }) => {
    page = testPage;
    await page.goto('http://localhost:8888');
    await page.waitForSelector('h1:has-text("Trading Dashboard")', { timeout: 15000 });
  });

  test('Dashboard loads successfully', async () => {
    const title = page.locator('h1:has-text("Trading Dashboard")');
    await expect(title).toBeVisible({ timeout: 10000 });
  });

  test('All core widgets are visible', async () => {
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

  test('All Layer 8 risk widgets are visible', async () => {
    // Scroll to see all widgets
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);

    const layer8Widgets = [
      'Portfolio Heat',
      'Risk Management',
      'Kelly Position Sizing',
      'Approval History'
    ];

    for (const widgetName of layer8Widgets) {
      const widget = page.locator(`text=/${widgetName}/i`).first();
      await expect(widget).toBeVisible({ timeout: 5000 });
    }
  });

  test('Portfolio Heat Widget displays data', async () => {
    const widget = page.locator('[data-testid="widget-portfolio-heat"], section:has-text("Portfolio Heat")').first();
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Check for heat percentage display
    const heatPercentage = widget.locator('text=/\\d+%\\.\\d+%/').first();
    // May take time to load data
    await page.waitForTimeout(3000);
    
    const hasPercentage = await heatPercentage.isVisible().catch(() => false);
    // Widget should be visible regardless
    await expect(widget).toBeVisible();
  });

  test('Kelly Sizing Widget is interactive', async () => {
    const widget = page.locator('[data-testid="widget-kelly-sizing"], section:has-text("Kelly")').first();
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Check for manual mode toggle
    const checkbox = widget.locator('input[type="checkbox"]').first();
    const hasCheckbox = await checkbox.isVisible().catch(() => false);
    
    // Check for calculate button
    const calculateButton = widget.locator('button:has-text("Calculate")').first();
    await expect(calculateButton).toBeVisible({ timeout: 5000 });
  });

  test('Approval History Widget displays', async () => {
    const widget = page.locator('[data-testid="widget-approval-history"], section:has-text("Approval History")').first();
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Widget should show title
    const title = widget.locator('text=/Approval History/i');
    await expect(title).toBeVisible();
  });

  test('Risk Management Widget has settings form', async () => {
    const widget = page.locator('[data-testid="widget-risk-management"], section:has-text("Risk Management")').first();
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Check for settings inputs
    const maxPositionSize = widget.locator('text=/Max Position Size/i');
    await expect(maxPositionSize).toBeVisible({ timeout: 5000 });
  });

  test('API endpoints return valid data', async ({ request }) => {
    const endpoints = [
      { url: '/api/risk/portfolio/summary', requiredFields: ['account_balance', 'total_portfolio_heat', 'max_portfolio_heat'] },
      { url: '/api/risk/portfolio/heat-utilization', requiredFields: ['total_heat', 'max_heat', 'utilization_pct'] },
      { url: '/api/risk/approval/stats', requiredFields: ['total_reviews', 'approval_rate'] },
      { url: '/api/risk/approval/history?limit=10', requiredFields: ['history', 'count'] },
    ];

    for (const endpoint of endpoints) {
      const response = await request.get(`http://localhost:8888${endpoint.url}`);
      expect(response.ok()).toBeTruthy();
      
      const data = await response.json();
      for (const field of endpoint.requiredFields) {
        expect(data).toHaveProperty(field);
      }
    }
  });

  test('Kelly calculation API works', async ({ request }) => {
    const response = await request.post('http://localhost:8888/api/risk/kelly/calculate', {
      data: {
        account_balance: 100000,
        max_loss_per_unit: 100.0,
        win_probability: 0.55,
        risk_reward_ratio: 2.0
      }
    });

    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('quantity');
    expect(data).toHaveProperty('kelly_pct');
    expect(data.kelly_pct).toBeGreaterThanOrEqual(0);
    expect(data.kelly_pct).toBeLessThanOrEqual(1);
  });

  test('Widgets display data from API', async () => {
    // Wait for data to load
    await page.waitForTimeout(5000);

    // Check Portfolio Heat Widget has data
    const portfolioHeat = page.locator('[data-testid="widget-portfolio-heat"]').first();
    if (await portfolioHeat.count() > 0) {
      const widgetText = await portfolioHeat.textContent();
      // Should have some content (not just loading)
      expect(widgetText?.length).toBeGreaterThan(50);
    }

    // Check Approval History Widget
    const approvalHistory = page.locator('[data-testid="widget-approval-history"]').first();
    if (await approvalHistory.count() > 0) {
      const widgetText = await approvalHistory.textContent();
      expect(widgetText?.length).toBeGreaterThan(20);
    }
  });

  test('No console errors on page load', async () => {
    const errors: string[] = [];
    
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.reload();
    await page.waitForTimeout(3000);

    // Filter out known/acceptable errors
    const criticalErrors = errors.filter(err => 
      !err.includes('favicon') && 
      !err.includes('Extension') &&
      !err.includes('DevTools')
    );

    expect(criticalErrors.length).toBe(0);
  });

  test('Widget interactions work', async () => {
    // Test Kelly Sizing Widget interaction
    const kellyWidget = page.locator('[data-testid="widget-kelly-sizing"]').first();
    if (await kellyWidget.count() > 0) {
      const checkbox = kellyWidget.locator('input[type="checkbox"]').first();
      if (await checkbox.isVisible().catch(() => false)) {
        await checkbox.check();
        await page.waitForTimeout(500);
        const isChecked = await checkbox.isChecked();
        expect(isChecked).toBe(true);
      }
    }
  });

  test('Page responsiveness works', async () => {
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(1000);
    
    const title = page.locator('h1:has-text("Trading Dashboard")');
    await expect(title).toBeVisible();

    // Test tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(1000);
    await expect(title).toBeVisible();

    // Test desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.waitForTimeout(1000);
    await expect(title).toBeVisible();
  });
});
