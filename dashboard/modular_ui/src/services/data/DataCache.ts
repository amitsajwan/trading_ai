/**
 * DataCache - In-memory cache with TTL support
 * 
 * Prevents UI flickering by maintaining cached data during WebSocket transitions.
 * Automatically expires entries after TTL.
 */

import { CacheEntry, DataCache as IDataCache } from './types'

const DEFAULT_TTL = 5 * 60 * 1000 // 5 minutes in milliseconds

export class DataCache<T = any> implements IDataCache<T> {
  private cache: Map<string, CacheEntry<T>> = new Map()
  private cleanupInterval: NodeJS.Timeout | null = null

  constructor(defaultTTL: number = DEFAULT_TTL) {
    this.defaultTTL = defaultTTL
    // Start cleanup interval to remove expired entries
    this.startCleanup()
  }

  private defaultTTL: number

  /**
   * Get cached value by key
   * Returns null if not found or expired
   */
  get(key: string): T | null {
    const entry = this.cache.get(key)
    
    if (!entry) {
      return null
    }

    // Check if expired
    const now = Date.now()
    const expiresAt = entry.timestamp + entry.ttl
    
    if (now > expiresAt) {
      // Entry expired, remove it
      this.cache.delete(key)
      return null
    }

    return entry.data
  }

  /**
   * Set cached value with optional TTL
   * @param key Cache key
   * @param value Value to cache
   * @param ttl Time to live in milliseconds (default: 5 minutes)
   */
  set(key: string, value: T, ttl?: number): void {
    const now = Date.now()
    const entry: CacheEntry<T> = {
      data: value,
      timestamp: now,
      ttl: ttl ?? this.defaultTTL,
    }

    this.cache.set(key, entry)
  }

  /**
   * Invalidate (remove) cached value
   */
  invalidate(key: string): void {
    this.cache.delete(key)
  }

  /**
   * Clear all cached values
   */
  clear(): void {
    this.cache.clear()
  }

  /**
   * Check if key exists and is valid (not expired)
   */
  has(key: string): boolean {
    const entry = this.cache.get(key)
    
    if (!entry) {
      return false
    }

    // Check if expired
    const now = Date.now()
    const expiresAt = entry.timestamp + entry.ttl
    
    if (now > expiresAt) {
      // Entry expired, remove it
      this.cache.delete(key)
      return false
    }

    return true
  }

  /**
   * Start cleanup interval to remove expired entries
   * Runs every minute
   */
  private startCleanup(): void {
    if (this.cleanupInterval) {
      return
    }

    this.cleanupInterval = setInterval(() => {
      this.cleanup()
    }, 60 * 1000) // Run cleanup every minute
  }

  /**
   * Stop cleanup interval
   */
  private stopCleanup(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval)
      this.cleanupInterval = null
    }
  }

  /**
   * Remove all expired entries
   */
  private cleanup(): void {
    const now = Date.now()
    const keysToDelete: string[] = []

    this.cache.forEach((entry, key) => {
      const expiresAt = entry.timestamp + entry.ttl
      if (now > expiresAt) {
        keysToDelete.push(key)
      }
    })

    keysToDelete.forEach((key) => {
      this.cache.delete(key)
    })
  }

  /**
   * Get cache size (number of entries)
   */
  size(): number {
    return this.cache.size
  }

  /**
   * Destroy cache and cleanup resources
   */
  destroy(): void {
    this.stopCleanup()
    this.clear()
  }
}

// Singleton instance (optional, can be instantiated per service)
export const defaultCache = new DataCache()
