/**
 * HTTPDataService Tests
 * 
 * Basic tests for HTTPDataService structure.
 * HTTPDataService is a thin wrapper around axios - full testing will happen
 * at the HybridDataService integration level where we can test real HTTP calls.
 */

import { describe, it, expect } from 'vitest'
import { HTTPDataService } from './HTTPDataService'

describe('HTTPDataService', () => {
  it('should create instance successfully', () => {
    const service = new HTTPDataService('http://test-api.com')
    expect(service).toBeInstanceOf(HTTPDataService)
  })

  it('should have fetch method', () => {
    const service = new HTTPDataService('http://test-api.com')
    expect(typeof service.fetch).toBe('function')
  })

  it('should have get method', () => {
    const service = new HTTPDataService('http://test-api.com')
    expect(typeof service.get).toBe('function')
  })

  it('should have post method', () => {
    const service = new HTTPDataService('http://test-api.com')
    expect(typeof service.post).toBe('function')
  })

  it('should export singleton instance', async () => {
    const { httpDataService } = await import('./HTTPDataService')
    expect(httpDataService).toBeInstanceOf(HTTPDataService)
  })
})
