/**
 * useMarketTick Tests
 * 
 * Tests for useMarketTick hook
 * 
 * @vitest-environment jsdom
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useMarketTick } from './useMarketTick'
import { httpDataService } from '../../services/data/HTTPDataService'

// Mock useWebSocket
vi.mock('../useWebSocket', () => ({
  useWebSocket: () => ({
    connected: true,
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
  }),
}))

// Mock httpDataService
vi.mock('../../services/data/HTTPDataService', () => ({
  httpDataService: {
    get: vi.fn(),
  },
}))

// Mock useData
const mockUseData = vi.fn()
vi.mock('./useData', () => ({
  useData: (options: any) => mockUseData(options),
}))

describe('useMarketTick', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should call useData with correct configuration', () => {
    mockUseData.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      isRealTime: false,
      status: 'fetching',
      refresh: vi.fn(),
    })

    renderHook(() => useMarketTick({ instrument: 'BANKNIFTY' }))

    expect(mockUseData).toHaveBeenCalledWith(
      expect.objectContaining({
        key: 'tick:BANKNIFTY',
        wsChannel: 'market:tick:BANKNIFTY:INDEX',
        cacheTTL: 5 * 60 * 1000, // 5 minutes
      })
    )
    
    // Verify fetchInitial function is provided
    const callArgs = mockUseData.mock.calls[0][0]
    expect(callArgs.fetchInitial).toBeDefined()
    expect(typeof callArgs.fetchInitial).toBe('function')
  })

  it('should use default instrument if not provided', () => {
    mockUseData.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      isRealTime: false,
      status: 'fetching',
      refresh: vi.fn(),
    })

    renderHook(() => useMarketTick())

    expect(mockUseData).toHaveBeenCalledWith(
      expect.objectContaining({
        key: 'tick:BANKNIFTY',
        wsChannel: 'market:tick:BANKNIFTY:INDEX',
      })
    )
  })

  it('should accept custom cacheTTL', () => {
    mockUseData.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      isRealTime: false,
      status: 'fetching',
      refresh: vi.fn(),
    })

    renderHook(() => useMarketTick({ instrument: 'NIFTY', cacheTTL: 10 * 60 * 1000 }))

    expect(mockUseData).toHaveBeenCalledWith(
      expect.objectContaining({
        key: 'tick:NIFTY',
        wsChannel: 'market:tick:NIFTY',
        cacheTTL: 10 * 60 * 1000,
      })
    )
  })

  it('should return useData result', () => {
    const mockResult = {
      data: { instrument: 'BANKNIFTY', last_price: 45000, timestamp: '2026-01-11T10:00:00Z' },
      loading: false,
      error: null,
      isRealTime: true,
      status: 'connected' as const,
      refresh: vi.fn(),
    }

    mockUseData.mockReturnValue(mockResult)

    const { result } = renderHook(() => useMarketTick({ instrument: 'BANKNIFTY' }))

    expect(result.current).toEqual(mockResult)
  })
})
