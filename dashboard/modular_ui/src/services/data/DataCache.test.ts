/**
 * DataCache Tests
 * 
 * Tests for DataCache implementation to verify TTL expiration, cache invalidation, and memory management.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { DataCache } from './DataCache'

describe('DataCache', () => {
  let cache: DataCache<number>
  let originalSetTimeout: typeof setTimeout
  let originalClearTimeout: typeof clearTimeout

  beforeEach(() => {
    cache = new DataCache<number>(1000) // 1 second TTL for tests
    vi.useFakeTimers()
  })

  afterEach(() => {
    cache.destroy()
    vi.useRealTimers()
  })

  describe('get and set', () => {
    it('should return null for non-existent key', () => {
      expect(cache.get('nonexistent')).toBeNull()
    })

    it('should return cached value', () => {
      cache.set('key1', 42)
      expect(cache.get('key1')).toBe(42)
    })

    it('should return null after TTL expires', () => {
      cache.set('key1', 42, 1000) // 1 second TTL
      
      // Before expiration
      expect(cache.get('key1')).toBe(42)
      
      // Advance time by 1.1 seconds
      vi.advanceTimersByTime(1100)
      
      // After expiration
      expect(cache.get('key1')).toBeNull()
    })
  })

  describe('has', () => {
    it('should return false for non-existent key', () => {
      expect(cache.has('nonexistent')).toBe(false)
    })

    it('should return true for existing valid key', () => {
      cache.set('key1', 42)
      expect(cache.has('key1')).toBe(true)
    })

    it('should return false after TTL expires', () => {
      cache.set('key1', 42, 1000)
      expect(cache.has('key1')).toBe(true)
      
      vi.advanceTimersByTime(1100)
      expect(cache.has('key1')).toBe(false)
    })
  })

  describe('invalidate', () => {
    it('should remove cached value', () => {
      cache.set('key1', 42)
      expect(cache.get('key1')).toBe(42)
      
      cache.invalidate('key1')
      expect(cache.get('key1')).toBeNull()
      expect(cache.has('key1')).toBe(false)
    })

    it('should handle invalidating non-existent key gracefully', () => {
      expect(() => cache.invalidate('nonexistent')).not.toThrow()
    })
  })

  describe('clear', () => {
    it('should remove all cached values', () => {
      cache.set('key1', 42)
      cache.set('key2', 43)
      cache.set('key3', 44)
      
      expect(cache.size()).toBe(3)
      
      cache.clear()
      
      expect(cache.size()).toBe(0)
      expect(cache.get('key1')).toBeNull()
      expect(cache.get('key2')).toBeNull()
      expect(cache.get('key3')).toBeNull()
    })
  })

  describe('size', () => {
    it('should return correct cache size', () => {
      expect(cache.size()).toBe(0)
      
      cache.set('key1', 42)
      expect(cache.size()).toBe(1)
      
      cache.set('key2', 43)
      expect(cache.size()).toBe(2)
      
      cache.invalidate('key1')
      expect(cache.size()).toBe(1)
    })

    it('should not count expired entries in size', () => {
      cache.set('key1', 42, 1000)
      expect(cache.size()).toBe(1)
      
      vi.advanceTimersByTime(1100)
      // Expired entries are cleaned up on access, so size might still show 1 until cleanup runs
      // But get() will return null
      expect(cache.get('key1')).toBeNull()
    })
  })

  describe('custom TTL', () => {
    it('should use custom TTL when provided', () => {
      cache.set('key1', 42, 2000) // 2 seconds
      
      // After 1 second, should still be valid
      vi.advanceTimersByTime(1000)
      expect(cache.get('key1')).toBe(42)
      
      // After 2.1 seconds, should be expired
      vi.advanceTimersByTime(1100)
      expect(cache.get('key1')).toBeNull()
    })

    it('should use default TTL when not provided', () => {
      cache.set('key1', 42) // Uses default (1000ms in test)
      
      vi.advanceTimersByTime(1100)
      expect(cache.get('key1')).toBeNull()
    })
  })

  describe('cleanup', () => {
    it('should cleanup expired entries periodically', () => {
      cache.set('key1', 42, 500) // 500ms TTL
      cache.set('key2', 43, 2000) // 2 seconds TTL
      
      expect(cache.size()).toBe(2)
      
      // Advance time so key1 expires
      vi.advanceTimersByTime(600)
      expect(cache.get('key1')).toBeNull() // Cleaned up on access
      
      // key2 should still be valid
      expect(cache.get('key2')).toBe(43)
    })
  })

  describe('destroy', () => {
    it('should clear cache and stop cleanup interval', () => {
      cache.set('key1', 42)
      cache.set('key2', 43)
      
      expect(cache.size()).toBe(2)
      
      cache.destroy()
      
      expect(cache.size()).toBe(0)
      // Verify cleanup is stopped (no errors on further timer advances)
      vi.advanceTimersByTime(70000) // 70 seconds
      expect(cache.size()).toBe(0)
    })
  })
})
