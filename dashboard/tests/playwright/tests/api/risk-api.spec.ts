import { test, expect } from '@playwright/test';

/**
 * Risk API Endpoints Tests
 * Tests Layer 8 Risk Management API endpoints
 */
const API_BASE = 'http://localhost:8888/api/risk';

test.describe('Risk Management API', () => {
  test('GET /api/risk/portfolio/summary should return portfolio heat summary', async ({ request }) => {
    const response = await request.get(`${API_BASE}/portfolio/summary`);
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    
    // Should have required fields
    expect(data).toHaveProperty('account_balance');
    expect(data).toHaveProperty('total_portfolio_heat');
    expect(data).toHaveProperty('max_portfolio_heat');
    expect(data).toHaveProperty('available_heat');
    expect(data).toHaveProperty('can_trade');
    
    // Heat should be between 0 and 1 (or percentage format)
    expect(typeof data.total_portfolio_heat).toBe('number');
    expect(data.total_portfolio_heat).toBeGreaterThanOrEqual(0);
  });

  test('GET /api/risk/portfolio/heat-utilization should return heat breakdown', async ({ request }) => {
    const response = await request.get(`${API_BASE}/portfolio/heat-utilization`);
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    
    // Should have utilization data
    expect(data).toHaveProperty('total_heat');
    expect(data).toHaveProperty('max_heat');
    expect(data).toHaveProperty('available_heat');
    expect(data).toHaveProperty('utilization_pct');
    expect(data).toHaveProperty('by_strategy');
    expect(data).toHaveProperty('by_instrument');
    
    // Utilization should be a percentage
    expect(typeof data.utilization_pct).toBe('number');
    expect(data.utilization_pct).toBeGreaterThanOrEqual(0);
    expect(data.utilization_pct).toBeLessThanOrEqual(100);
  });

  test('POST /api/risk/kelly/calculate should calculate Kelly position size', async ({ request }) => {
    const response = await request.post(`${API_BASE}/kelly/calculate`, {
      data: {
        account_balance: 100000,
        max_loss_per_unit: 100.0,
        win_probability: 0.55,
        risk_reward_ratio: 2.0
      }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    
    // Should return Kelly calculation
    expect(data).toHaveProperty('quantity');
    expect(data).toHaveProperty('kelly_pct');
    expect(data).toHaveProperty('risk_amount');
    expect(data).toHaveProperty('historical_stats');
    
    // Kelly percentage should be between 0 and 1
    expect(data.kelly_pct).toBeGreaterThanOrEqual(0);
    expect(data.kelly_pct).toBeLessThanOrEqual(1);
  });

  test('GET /api/risk/approval/history should return approval history', async ({ request }) => {
    const response = await request.get(`${API_BASE}/approval/history?limit=10`);
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    
    // Should have history structure
    expect(data).toHaveProperty('history');
    expect(data).toHaveProperty('count');
    
    expect(Array.isArray(data.history)).toBe(true);
    expect(typeof data.count).toBe('number');
  });

  test('GET /api/risk/approval/stats should return approval statistics', async ({ request }) => {
    const response = await request.get(`${API_BASE}/approval/stats`);
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    
    // Should have stats
    expect(data).toHaveProperty('total_reviews');
    expect(data).toHaveProperty('approved');
    expect(data).toHaveProperty('rejected');
    expect(data).toHaveProperty('approval_rate');
    expect(data).toHaveProperty('rejection_rate');
    
    // Rates should be between 0 and 1
    expect(data.approval_rate).toBeGreaterThanOrEqual(0);
    expect(data.approval_rate).toBeLessThanOrEqual(1);
    expect(data.rejection_rate).toBeGreaterThanOrEqual(0);
    expect(data.rejection_rate).toBeLessThanOrEqual(1);
  });

  test('POST /api/risk/portfolio/can-open-position should check position approval', async ({ request }) => {
    const response = await request.post(`${API_BASE}/portfolio/can-open-position`, {
      params: {
        proposed_max_loss: 1000.0
      }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    
    // Should return approval decision
    expect(data).toHaveProperty('can_open');
    expect(data).toHaveProperty('reason');
    
    expect(typeof data.can_open).toBe('boolean');
    expect(typeof data.reason).toBe('string');
  });
});
