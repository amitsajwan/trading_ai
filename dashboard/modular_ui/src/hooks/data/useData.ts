/**
 * useData - Generic hook for data subscriptions
 * 
 * This hook bridges HybridDataService with React components.
 * 
 * Features:
 * - Seamless HTTP + WebSocket integration
 * - No flickering (uses cached data during transitions)
 * - Automatic cleanup on unmount
 * - Loading and error states
 * 
 * Usage:
 * ```tsx
 * const { data, loading, error, isRealTime } = useData({
 *   key: 'tick:BANKNIFTY',
 *   fetchInitial: () => httpService.get('/api/market-data/tick/BANKNIFTY'),
 *   wsChannel: 'market:tick:BANKNIFTY',
 * })
 * ```
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useWebSocket } from '../useWebSocket'
import { HybridDataService } from '../../services/data/HybridDataService'
// import { HTTPDataService } from '../../services/data/HTTPDataService' // DISABLED: No HTTP fallbacks
import { WebSocketDataService } from '../../services/data/WebSocketDataService'
import { DataCache } from '../../services/data/DataCache'
import { messageRouter } from '../../services/data/WebSocketMessageRouter'
import type { UseDataResult, DataServiceStatus, DataCache as IDataCache } from '../../services/data/types'

interface UseDataOptions<T> {
  /**
   * Unique key for this data (e.g., "tick:BANKNIFTY")
   */
  key: string

  /**
   * Function to fetch initial data via HTTP
   */
  fetchInitial: () => Promise<T>

  /**
   * WebSocket channel pattern (e.g., "market:tick:BANKNIFTY")
   * If not provided, data will only be fetched via HTTP
   */
  wsChannel?: string

  /**
   * Cache TTL in milliseconds
   * Default: 5 minutes
   */
  cacheTTL?: number

  /**
   * Whether to fetch initial data on subscribe
   * Default: true
   */
  fetchOnSubscribe?: boolean

  /**
   * Custom HybridDataService instance (optional)
   * If not provided, creates a new instance
   */
  dataService?: HybridDataService<T>
}

// Shared service instances (can be customized per app)
// let sharedHttpService: HTTPDataService | null = null // DISABLED: No HTTP fallbacks
let sharedWsService: WebSocketDataService | null = null
let sharedCache: IDataCache<any> | null = null

function getSharedServices() {
  // if (!sharedHttpService) {
  //   sharedHttpService = new HTTPDataService()
  // } // DISABLED: No HTTP fallbacks
  if (!sharedWsService) {
    sharedWsService = new WebSocketDataService()
  }
  if (!sharedCache) {
    sharedCache = new DataCache()
  }
  return { sharedWsService, sharedCache }
}

/**
 * useData hook - Subscribe to data with HTTP + WebSocket support
 */
export function useData<T = any>(options: UseDataOptions<T>): UseDataResult<T> {
  const { key, fetchInitial, wsChannel, cacheTTL, fetchOnSubscribe, dataService: customService } = options

  // Get WebSocket context
  const { connected: wsConnected, subscribe: wsSubscribe, unsubscribe: wsUnsubscribe } = useWebSocket()

  // State
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [isRealTime, setIsRealTime] = useState(false)
  const [status, setStatus] = useState<DataServiceStatus>('idle')

  // Service instance (created once per hook call)
  const serviceRef = useRef<HybridDataService<T> | null>(null)
  const unsubscribeRef = useRef<(() => void) | null>(null)

  // Initialize service
  useEffect(() => {
    try {
      if (!serviceRef.current) {
        if (customService) {
          serviceRef.current = customService
        } else {
          const { sharedWsService, sharedCache } = getSharedServices()
            serviceRef.current = new HybridDataService<T>(
              undefined, // DISABLED: No HTTP service
              sharedWsService,
              sharedCache as IDataCache<T>
            )
        }

        // Initialize WebSocket service
        serviceRef.current.initializeWebSocket({
          subscribe: wsSubscribe,
          unsubscribe: wsUnsubscribe,
          isConnected: () => wsConnected,
          onMessage: (channel: string, messageData: any) => {
            // Route messages to HybridDataService's WebSocketDataService
            try {
              serviceRef.current?.handleWebSocketMessage(channel, messageData)
            } catch (err) {
              console.error(`Error handling WS message for channel ${channel}:`, err)
            }
          },
        })
      }
    } catch (err) {
      console.error(`Error initializing data service for key ${key}:`, err)
      const error = err instanceof Error ? err : new Error(String(err))
      setError(error)
      setLoading(false)
      setStatus('error')
    }

    return () => {
      // Cleanup will happen in the subscribe effect
    }
  }, [customService, wsSubscribe, wsUnsubscribe, wsConnected, key])

  // Wrap fetchInitial to handle errors gracefully (memoized to prevent re-subscriptions)
  const safeFetchInitial = useCallback(async () => {
    try {
      return await fetchInitial()
    } catch (err) {
      console.error(`Error fetching initial data for key ${key}:`, err)
      const error = err instanceof Error ? err : new Error(String(err))
      setError(error)
      setLoading(false)
      setStatus('error')
      throw error // Re-throw so HybridDataService knows fetch failed
    }
  }, [fetchInitial, key])

  // Subscribe to data
  useEffect(() => {
    if (!serviceRef.current) return

    try {
      const service = serviceRef.current

      // Check if we have cached data
      const cachedData = service.getCurrent(key)
      if (cachedData) {
        setData(cachedData)
        setLoading(false)
        setError(null)
      }

      // Register message router handler for this channel
      let routerUnsubscribe: (() => void) | null = null
      if (wsChannel) {
        try {
          routerUnsubscribe = messageRouter.on(wsChannel, (channel: string, data: any) => {
            try {
              service.handleWebSocketMessage(channel, data)
            } catch (err) {
              console.error(`Error in message router handler for channel ${channel}:`, err)
            }
          })
        } catch (err) {
          console.error(`Error registering message router for channel ${wsChannel}:`, err)
        }
      }

      // Subscribe to data updates (DISABLED HTTP fallback - only WebSocket)
      const unsubscribe = service.subscribe(
        key,
        (newData: T) => {
          try {
            setData(newData)
            setLoading(false)
            setError(null)
            setIsRealTime(wsConnected && !!wsChannel)
            setStatus(wsConnected ? 'connected' : 'idle') // Changed from 'fetching' to 'idle'
          } catch (err) {
            console.error(`Error in data callback for key ${key}:`, err)
            const error = err instanceof Error ? err : new Error(String(err))
            setError(error)
            setLoading(false)
            setStatus('error')
          }
        },
        {
          // fetchInitial: safeFetchInitial, // DISABLED: No HTTP fallbacks
          wsChannel,
          cacheTTL,
          fetchOnSubscribe: false, // DISABLED: No HTTP fetching on subscribe
        }
      )

      unsubscribeRef.current = unsubscribe

      // Set loading state if no cached data
      if (!cachedData && fetchOnSubscribe !== false) {
        setLoading(true)
        setStatus('fetching')
      }

      // Cleanup on unmount or key change
      return () => {
        try {
          unsubscribe()
          if (routerUnsubscribe) {
            routerUnsubscribe()
          }
          unsubscribeRef.current = null
        } catch (err) {
          console.error(`Error cleaning up subscription for key ${key}:`, err)
        }
      }
    } catch (err) {
      console.error(`Error subscribing to data for key ${key}:`, err)
      const error = err instanceof Error ? err : new Error(String(err))
      setError(error)
      setLoading(false)
      setStatus('error')
    }
  }, [key, safeFetchInitial, wsChannel, cacheTTL, fetchOnSubscribe, wsConnected])

  // Update WebSocket connection status
  useEffect(() => {
    if (serviceRef.current) {
      serviceRef.current.setWebSocketConnected(wsConnected)
      
      // Update isRealTime status
      if (wsConnected && wsChannel) {
        setIsRealTime(true)
        setStatus('connected')
      } else if (!wsConnected) {
        setIsRealTime(false)
        setStatus('fetching')
      }
    }
  }, [wsConnected, wsChannel])

  // Handle fetch errors
  useEffect(() => {
    // Errors are caught in fetchInitial, but we need to handle them
    // This will be improved when we add error handling to HybridDataService
  }, [])

  // Manual refresh function (DISABLED - no HTTP fallbacks)
  const refresh = useCallback(async () => {
    // DISABLED: No HTTP refresh functionality
    console.warn('Refresh disabled: No HTTP fallbacks enabled')
    return
  }, [])

  return {
    data,
    loading,
    error,
    isRealTime,
    status,
    refresh,
  }
}
