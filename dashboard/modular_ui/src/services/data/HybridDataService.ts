/**
 * HybridDataService - Combines HTTP + WebSocket seamlessly
 * 
 * This is the core service that prevents UI flickering.
 * 
 * Behavior:
 * 1. On subscribe: Returns cached data immediately (if exists)
 * 2. Fetches initial data via HTTP (if not cached)
 * 3. Subscribes to WebSocket for real-time updates
 * 4. On WS disconnect: Continues with cached data (no flickering)
 * 5. On WS reconnect: Smoothly transitions back to real-time
 */

import { DataService, SubscribeOptions, DataCache } from './types'
import { HTTPDataService } from './HTTPDataService'
import { WebSocketDataService } from './WebSocketDataService'
import { DataCache as DataCacheImpl } from './DataCache'

export class HybridDataService<T = any> implements DataService<T> {
  private httpService: HTTPDataService
  private wsService: WebSocketDataService
  private cache: DataCache<T>
  private channelToKeyMap: Map<string, string> = new Map()

  constructor(
    httpService?: HTTPDataService,
    wsService?: WebSocketDataService,
    cache?: DataCache<T>
  ) {
    this.httpService = httpService || new HTTPDataService()
    this.wsService = wsService || new WebSocketDataService()
    this.cache = cache || (new DataCacheImpl<T>() as DataCache<T>)
  }

  /**
   * Initialize WebSocket service with subscription functions
   */
  initializeWebSocket(options: {
    subscribe: (channels: string[]) => void
    unsubscribe: (channels: string[]) => void
    isConnected: () => boolean
    onMessage: (channel: string, data: any) => void
  }) {
    this.wsService.initialize(options)
  }

  /**
   * Subscribe to data updates
   * 
   * @param key Unique identifier (e.g., "tick:BANKNIFTY")
   * @param callback Function to call when data updates
   * @param options Subscription options (fetch initial, WS channel, cache TTL)
   * @returns Unsubscribe function
   */
  subscribe(
    key: string,
    callback: (data: T) => void,
    options?: SubscribeOptions<T>
  ): () => void {
    const wsChannel = options?.wsChannel
    const cacheTTL = options?.cacheTTL
    const fetchOnSubscribe = options?.fetchOnSubscribe !== false // Default: true

    // 1. Return cached data immediately (if exists) - prevents flickering
    const cachedData = this.cache.get(key)
    if (cachedData) {
      callback(cachedData)
    }

    // 2. Set up WebSocket subscription (if channel provided)
    let wsUnsubscribe: (() => void) | null = null
    if (wsChannel) {
      // Map channel to key for cache updates
      this.channelToKeyMap.set(wsChannel, key)

      wsUnsubscribe = this.wsService.subscribe(wsChannel, (data: T) => {
        // Update cache with new data
        this.cache.set(key, data, cacheTTL)
        // Call callback with new data
        callback(data)
      })
    }

    // 3. Fetch initial data if not cached and fetchOnSubscribe is true
    let isFetching = false
    if (fetchOnSubscribe && !cachedData && options?.fetchInitial) {
      isFetching = true
      options
        .fetchInitial()
        .then((data: T) => {
          // Update cache
          this.cache.set(key, data, cacheTTL)
          // Call callback with fetched data
          callback(data)
        })
        .catch((error) => {
          console.error(`Failed to fetch initial data for key ${key}:`, error)
          // Don't call callback on error - component should handle loading/error states
        })
        .finally(() => {
          isFetching = false
        })
    }

    // Return unsubscribe function
    return () => {
      if (wsUnsubscribe) {
        wsUnsubscribe()
        // Remove channel mapping
        if (wsChannel) {
          this.channelToKeyMap.delete(wsChannel)
        }
      }
    }
  }

  /**
   * Get current cached value
   */
  getCurrent(key: string): T | null {
    return this.cache.get(key)
  }

  /**
   * Fetch initial data (typically via HTTP)
   */
  async fetchInitial(key: string, options?: { force?: boolean }): Promise<T> {
    // If not forcing and data is cached, return cached data
    if (!options?.force) {
      const cached = this.cache.get(key)
      if (cached) {
        return cached
      }
    }

    // Fetch via HTTP (this should be provided by the caller via SubscribeOptions.fetchInitial)
    throw new Error(
      `fetchInitial called without fetchInitial function in SubscribeOptions for key ${key}`
    )
  }

  /**
   * Update connection status
   */
  setWebSocketConnected(connected: boolean): void {
    this.wsService.setConnected(connected)
  }

  /**
   * Handle incoming WebSocket message
   */
  handleWebSocketMessage(channel: string, data: any): void {
    this.wsService.handleMessage(channel, data)
  }
}

// Singleton instance (optional, can be instantiated per data type)
export const defaultHybridDataService = new HybridDataService()
