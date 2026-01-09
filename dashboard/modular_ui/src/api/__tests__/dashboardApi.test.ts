import { describe, it, expect } from 'vitest'
import { dashboardApi } from '../dashboardApi'

describe('dashboardApi', () => {
  it('exports expected endpoints', () => {
    const endpoints = Object.keys((dashboardApi as any).endpoints)
    expect(endpoints).toContain('getHealth')
    expect(endpoints).toContain('getRecentTrades')
    expect(endpoints).toContain('getPortfolio')
    expect(endpoints).toContain('getAgentStatus')
  })
})
