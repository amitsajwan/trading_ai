/**
 * useMarketTick - Hook for market tick data
 * 
 * Wraps useData with tick-specific configuration.
 * 
 * Usage:
 * ```tsx
 * const { data, loading, error, isRealTime } = useMarketTick('BANKNIFTY')
 * ```
 */

import { useCallback } from 'react'
import { useData } from './useData'
// import { httpDataService } from '../../services/data/HTTPDataService' // DISABLED: No HTTP fallbacks
import type { TickData } from '../../store/slices/marketDataSlice'

export interface UseMarketTickOptions {
  /**
   * Instrument symbol (e.g., 'BANKNIFTY', 'NIFTY')
   * @default 'BANKNIFTY'
   */
  instrument?: string

  /**
   * Cache TTL in milliseconds
   * @default 5 minutes
   */
  cacheTTL?: number

  /**
   * Whether to fetch initial data on subscribe
   * @default true
   */
  fetchOnSubscribe?: boolean
}

/**
 * Hook for market tick data
 */
export function useMarketTick(options: UseMarketTickOptions = {}) {
  const { instrument = 'BANKNIFTY', cacheTTL, fetchOnSubscribe } = options

  // Memoize fetchInitial (DISABLED - no HTTP fetching)
  const fetchInitial = useCallback(async () => {
    // DISABLED: No HTTP fallbacks - throw error to indicate no data available
    throw new Error(`HTTP fetching disabled for ${instrument}`)
  }, [instrument])

  return useData<TickData>({
    key: `tick:${instrument}`,
    // fetchInitial, // DISABLED: No HTTP fallbacks
    wsChannel: `market:tick:${instrument}`,
    cacheTTL: cacheTTL ?? 5 * 60 * 1000, // 5 minutes default
    fetchOnSubscribe: false, // DISABLED: No HTTP fetching on subscribe
  })
}
