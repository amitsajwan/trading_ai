/**
 * Data Service Types
 * 
 * Defines interfaces for the data layer abstraction.
 * Components use these interfaces via hooks, without knowing about HTTP vs WebSocket.
 */

/**
 * Generic data service interface
 * Implementations can use HTTP, WebSocket, or both
 */
export interface DataService<T = any> {
  /**
   * Subscribe to data updates for a given key
   * @param key Unique identifier for the data (e.g., "tick:BANKNIFTY")
   * @param callback Function to call when data updates
   * @param options Subscription options (fetch initial, WS channel, etc.)
   * @returns Unsubscribe function
   */
  subscribe(
    key: string,
    callback: (data: T) => void,
    options?: SubscribeOptions<T>
  ): () => void

  /**
   * Get current cached value for a key
   * Returns null if not cached
   */
  getCurrent(key: string): T | null

  /**
   * Fetch initial data (typically via HTTP)
   * Used when subscribing to a key that's not cached
   */
  fetchInitial(key: string, options?: FetchOptions): Promise<T>
}

/**
 * Options for subscribing to data
 */
export interface SubscribeOptions<T = any> {
  /**
   * Function to fetch initial data if not cached
   * If provided, will be called before subscribing to WS updates
   */
  fetchInitial?: () => Promise<T>

  /**
   * WebSocket channel pattern (e.g., "market:tick:BANKNIFTY")
   * Used by WebSocketDataService to subscribe to WS updates
   */
  wsChannel?: string

  /**
   * Cache TTL in milliseconds
   * Default: 5 minutes
   */
  cacheTTL?: number

  /**
   * Whether to immediately fetch initial data on subscribe
   * Default: true
   */
  fetchOnSubscribe?: boolean
}

/**
 * Options for fetching data
 */
export interface FetchOptions {
  /**
   * Force fetch (bypass cache)
   * Default: false
   */
  force?: boolean

  /**
   * Cache TTL for fetched data
   */
  cacheTTL?: number
}

/**
 * Cache entry with expiration
 */
export interface CacheEntry<T> {
  data: T
  timestamp: number
  ttl: number
}

/**
 * Data cache interface
 * In-memory cache with TTL support
 */
export interface DataCache<T = any> {
  /**
   * Get cached value by key
   * Returns null if not found or expired
   */
  get(key: string): T | null

  /**
   * Set cached value with optional TTL
   * @param key Cache key
   * @param value Value to cache
   * @param ttl Time to live in milliseconds (default: 5 minutes)
   */
  set(key: string, value: T, ttl?: number): void

  /**
   * Invalidate (remove) cached value
   */
  invalidate(key: string): void

  /**
   * Clear all cached values
   */
  clear(): void

  /**
   * Check if key exists and is valid (not expired)
   */
  has(key: string): boolean
}

/**
 * Data service status
 */
export type DataServiceStatus = 'idle' | 'fetching' | 'connected' | 'disconnected' | 'error'

/**
 * Hook return type for data hooks
 */
export interface UseDataResult<T> {
  /**
   * Current data value (null if not loaded)
   */
  data: T | null

  /**
   * Whether data is currently loading
   */
  loading: boolean

  /**
   * Error if any occurred
   */
  error: Error | null

  /**
   * Whether data is from real-time source (WebSocket)
   * false means data is from cache or HTTP
   */
  isRealTime: boolean

  /**
   * Current service status
   */
  status: DataServiceStatus

  /**
   * Manually refresh data (fetch from HTTP)
   */
  refresh: () => Promise<void>
}
