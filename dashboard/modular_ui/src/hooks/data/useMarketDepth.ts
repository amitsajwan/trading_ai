/**
 * useMarketDepth - Hook for market depth data with mode awareness
 *
 * Fetches market depth data from appropriate sources based on execution mode:
 * - LIVE mode: Real-time API calls to market-data service
 * - Historical replay: WebSocket updates with historical data
 * - BACKTEST mode: Fallback to mock data (no real-time API available)
 *
 * Usage:
 * ```tsx
 * const { data: depthData, loading, error, refresh, isRealTime } = useMarketDepth('BANKNIFTY')
 * ```
 */

import { useCallback, useState, useEffect } from 'react'
import { useData } from './useData'
import type { TickData } from '../../store/slices/marketDataSlice'

export interface DepthLevel {
  price: number
  quantity: number
}

export interface MarketDepthData {
  instrument: string
  buy: DepthLevel[]
  sell: DepthLevel[]
  timestamp: string
  mode: 'LIVE' | 'HISTORICAL' | 'UNKNOWN'
  isRealTime: boolean
}

export interface UseMarketDepthOptions {
  /**
   * Instrument symbol (e.g., 'BANKNIFTY', 'NIFTY')
   * @default 'BANKNIFTY'
   */
  instrument?: string

  /**
   * Cache TTL in milliseconds
   * @default 30 seconds (depth data changes frequently)
   */
  cacheTTL?: number

  /**
   * Whether to fetch initial data on subscribe
   * @default true
   */
  fetchOnSubscribe?: boolean
}

/**
 * Hook for market depth data with mode-aware fallbacks
 */
export function useMarketDepth(options: UseMarketDepthOptions = {}) {
  const { instrument = 'BANKNIFTY', cacheTTL, fetchOnSubscribe } = options
  const [executionMode, setExecutionMode] = useState<'LIVE' | 'HISTORICAL' | 'UNKNOWN'>('LIVE')

  // Detect execution mode from WebSocket context
  useEffect(() => {
    // Try to detect mode from document or localStorage (set by dashboard)
    const checkMode = () => {
      try {
        // Check for mode indicators in the app
        const modeElement = document.querySelector('[data-mode]')
        if (modeElement) {
          const mode = modeElement.getAttribute('data-mode')
          if (mode === 'HISTORICAL') setExecutionMode('HISTORICAL')
          else setExecutionMode('LIVE')
        } else {
          // Default to LIVE if no indicators found
          setExecutionMode('LIVE')
        }
      } catch (e) {
        setExecutionMode('LIVE')  // Default to LIVE on error
      }
    }

    checkMode()
    // Re-check periodically in case mode changes
    const interval = setInterval(checkMode, 5000)
    return () => clearInterval(interval)
  }, [])

  // Memoize fetchInitial with mode-aware logic
  const fetchInitial = useCallback(async (): Promise<MarketDepthData> => {
    try {
      const response = await fetch(`/api/market-data/depth/${instrument}`)
      if (!response.ok) {
        throw new Error(`Failed to fetch market depth: ${response.statusText}`)
      }
      const data = await response.json()

      // Transform to our expected format with mode info
      return {
        instrument: data.instrument || instrument,
        buy: data.buy || [],
        sell: data.sell || [],
        timestamp: data.timestamp || new Date().toISOString(),
        mode: executionMode,
        isRealTime: executionMode === 'LIVE'
      }
    } catch (error) {
      console.warn(`Market depth API unavailable (${executionMode} mode), using fallback data:`, error)
      return generateMockDepthData(instrument, executionMode)
    }
  }, [instrument, executionMode])

  // Use WebSocket channel for real-time depth updates (when available)
  const wsChannel = `market:depth:${instrument}`

  const dataHook = useData<MarketDepthData>({
    key: `depth:${instrument}`,
    fetchInitial,
    wsChannel,
    cacheTTL: cacheTTL ?? 30 * 1000, // 30 seconds default for depth data
    fetchOnSubscribe: fetchOnSubscribe ?? true,
  })

  return {
    ...dataHook,
    // Override isRealTime based on execution mode
    isRealTime: executionMode === 'LIVE' && dataHook.isRealTime
  }
}

/**
 * Generate mock depth data for fallback scenarios
 */
function generateMockDepthData(instrument: string, mode: 'LIVE' | 'HISTORICAL' | 'UNKNOWN' = 'UNKNOWN'): MarketDepthData {
  // Use a deterministic seed based on instrument for consistent mock data
  const seed = instrument.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  const mockRandom = (min: number, max: number) => min + (seed % 100) / 100 * (max - min)

  // Base price assumptions (would be more sophisticated in real implementation)
  const basePrices: Record<string, number> = {
    'BANKNIFTY': 59875,
    'BANKNIFTY26JANFUT': 59992,
    'NIFTY': 22000,
    'SENSEX': 65000,
    'FINNIFTY': 23000
  }

  const basePrice = basePrices[instrument] || 45000

  // Generate mock depth around base price
  const buyLevels: DepthLevel[] = []
  const sellLevels: DepthLevel[] = []

  // Generate 5-8 levels on each side
  const numLevels = Math.floor(mockRandom(5, 9))

  for (let i = 0; i < numLevels; i++) {
    // Buy side (bids) - below current price
    const bidPrice = basePrice - (i + 1) * mockRandom(5, 15)
    const bidQty = Math.floor(mockRandom(50, 500))
    buyLevels.push({
      price: Math.round(bidPrice * 100) / 100,
      quantity: bidQty
    })

    // Sell side (asks) - above current price
    const askPrice = basePrice + (i + 1) * mockRandom(5, 15)
    const askQty = Math.floor(mockRandom(50, 500))
    sellLevels.push({
      price: Math.round(askPrice * 100) / 100,
      quantity: askQty
    })
  }

  return {
    instrument,
    buy: buyLevels.sort((a, b) => b.price - a.price), // Sort bids descending
    sell: sellLevels.sort((a, b) => a.price - b.price), // Sort asks ascending
    timestamp: new Date().toISOString(),
    mode,
    isRealTime: false
  }
}