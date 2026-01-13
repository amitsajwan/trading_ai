/**
 * WebSocketDataService Tests
 * 
 * Tests for WebSocketDataService subscription management.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { WebSocketDataService } from './WebSocketDataService'

describe('WebSocketDataService', () => {
  let service: WebSocketDataService
  let mockSubscribe: ReturnType<typeof vi.fn>
  let mockUnsubscribe: ReturnType<typeof vi.fn>
  let mockOnMessage: ReturnType<typeof vi.fn>

  beforeEach(() => {
    service = new WebSocketDataService()
    mockSubscribe = vi.fn()
    mockUnsubscribe = vi.fn()
    mockOnMessage = vi.fn()

    service.initialize({
      subscribe: mockSubscribe,
      unsubscribe: mockUnsubscribe,
      isConnected: () => true,
      onMessage: mockOnMessage,
    })
  })

  describe('subscribe', () => {
    it('should add callback to subscription', () => {
      const callback = vi.fn()
      const unsubscribe = service.subscribe('market:tick:BANKNIFTY', callback)

      expect(service.getSubscribedChannels()).toContain('market:tick:BANKNIFTY')
      expect(mockSubscribe).toHaveBeenCalledWith(['market:tick:BANKNIFTY'])
      
      unsubscribe()
    })

    it('should call subscribe function when connected', () => {
      const callback = vi.fn()
      service.subscribe('market:tick:BANKNIFTY', callback)

      expect(mockSubscribe).toHaveBeenCalledWith(['market:tick:BANKNIFTY'])
    })

    it('should return unsubscribe function', () => {
      const callback = vi.fn()
      const unsubscribe = service.subscribe('market:tick:BANKNIFTY', callback)

      expect(typeof unsubscribe).toBe('function')

      unsubscribe()
      expect(service.getSubscribedChannels()).not.toContain('market:tick:BANKNIFTY')
    })

    it('should support multiple callbacks for same channel', () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()

      const unsubscribe1 = service.subscribe('market:tick:BANKNIFTY', callback1)
      const unsubscribe2 = service.subscribe('market:tick:BANKNIFTY', callback2)

      expect(service.getSubscribedChannels()).toContain('market:tick:BANKNIFTY')
      expect(mockSubscribe).toHaveBeenCalledTimes(1) // Only one subscribe call

      unsubscribe1()
      // Should still be subscribed (callback2 still active)
      expect(service.getSubscribedChannels()).toContain('market:tick:BANKNIFTY')

      unsubscribe2()
      // Now should be unsubscribed
      expect(service.getSubscribedChannels()).not.toContain('market:tick:BANKNIFTY')
      expect(mockUnsubscribe).toHaveBeenCalledWith(['market:tick:BANKNIFTY'])
    })
  })

  describe('handleMessage', () => {
    it('should call callback when message arrives', () => {
      const callback = vi.fn()
      service.subscribe('market:tick:BANKNIFTY', callback)

      const messageData = { price: 45000 }
      service.handleMessage('market:tick:BANKNIFTY', messageData)

      expect(callback).toHaveBeenCalledWith(messageData)
    })

    it('should call all callbacks for channel', () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()

      service.subscribe('market:tick:BANKNIFTY', callback1)
      service.subscribe('market:tick:BANKNIFTY', callback2)

      const messageData = { price: 45000 }
      service.handleMessage('market:tick:BANKNIFTY', messageData)

      expect(callback1).toHaveBeenCalledWith(messageData)
      expect(callback2).toHaveBeenCalledWith(messageData)
    })

    it('should not call callback after unsubscribe', () => {
      const callback = vi.fn()
      const unsubscribe = service.subscribe('market:tick:BANKNIFTY', callback)

      unsubscribe()

      service.handleMessage('market:tick:BANKNIFTY', { price: 45000 })
      expect(callback).not.toHaveBeenCalled()
    })

    it('should handle errors in callbacks gracefully', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const callback = vi.fn(() => {
        throw new Error('Callback error')
      })

      service.subscribe('market:tick:BANKNIFTY', callback)

      expect(() => {
        service.handleMessage('market:tick:BANKNIFTY', { price: 45000 })
      }).not.toThrow()

      expect(consoleErrorSpy).toHaveBeenCalled()
      consoleErrorSpy.mockRestore()
    })
  })

  describe('channel matching', () => {
    it('should match exact channels', () => {
      const callback = vi.fn()
      service.subscribe('market:tick:BANKNIFTY', callback)

      service.handleMessage('market:tick:BANKNIFTY', { price: 45000 })
      expect(callback).toHaveBeenCalled()
    })

    it('should match wildcard patterns', () => {
      const callback = vi.fn()
      service.subscribe('market:tick:*', callback)

      service.handleMessage('market:tick:BANKNIFTY', { price: 45000 })
      service.handleMessage('market:tick:NIFTY', { price: 20000 })

      expect(callback).toHaveBeenCalledTimes(2)
    })
  })

  describe('setConnected', () => {
    it('should resubscribe to all channels when connected', () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()

      service.subscribe('market:tick:BANKNIFTY', callback1)
      service.subscribe('market:options:*', callback2)

      // Disconnect
      service.setConnected(false)
      mockSubscribe.mockClear()

      // Reconnect
      service.setConnected(true)

      expect(mockSubscribe).toHaveBeenCalledWith([
        'market:tick:BANKNIFTY',
        'market:options:*',
      ])
    })
  })

  describe('clear', () => {
    it('should clear all subscriptions', () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()

      service.subscribe('market:tick:BANKNIFTY', callback1)
      service.subscribe('market:options:*', callback2)

      expect(service.getSubscribedChannels().length).toBe(2)

      service.clear()

      expect(service.getSubscribedChannels().length).toBe(0)
      expect(mockUnsubscribe).toHaveBeenCalledWith([
        'market:tick:BANKNIFTY',
        'market:options:*',
      ])
    })
  })
})
