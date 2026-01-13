/**
 * WebSocketMessageRouter Tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { WebSocketMessageRouter } from './WebSocketMessageRouter'

describe('WebSocketMessageRouter', () => {
  let router: WebSocketMessageRouter

  beforeEach(() => {
    router = new WebSocketMessageRouter()
  })

  describe('on and route', () => {
    it('should call handler when message arrives', () => {
      const handler = vi.fn()
      router.on('market:tick:BANKNIFTY', handler)

      router.route('market:tick:BANKNIFTY', { price: 45000 })

      expect(handler).toHaveBeenCalledWith('market:tick:BANKNIFTY', { price: 45000 })
    })

    it('should support multiple handlers for same channel', () => {
      const handler1 = vi.fn()
      const handler2 = vi.fn()

      router.on('market:tick:BANKNIFTY', handler1)
      router.on('market:tick:BANKNIFTY', handler2)

      router.route('market:tick:BANKNIFTY', { price: 45000 })

      expect(handler1).toHaveBeenCalled()
      expect(handler2).toHaveBeenCalled()
    })

    it('should not call handler after unsubscribe', () => {
      const handler = vi.fn()
      const unsubscribe = router.on('market:tick:BANKNIFTY', handler)

      unsubscribe()

      router.route('market:tick:BANKNIFTY', { price: 45000 })
      expect(handler).not.toHaveBeenCalled()
    })
  })

  describe('onAll', () => {
    it('should call wildcard handler for all messages', () => {
      const handler = vi.fn()
      router.onAll(handler)

      router.route('market:tick:BANKNIFTY', { price: 45000 })
      router.route('market:options:*', { strikes: [] })

      expect(handler).toHaveBeenCalledTimes(2)
    })
  })

  describe('wildcard pattern matching', () => {
    it('should match wildcard patterns', () => {
      const handler = vi.fn()
      router.on('market:tick:*', handler)

      router.route('market:tick:BANKNIFTY', { price: 45000 })
      router.route('market:tick:NIFTY', { price: 20000 })

      expect(handler).toHaveBeenCalledTimes(2)
    })
  })

  describe('clear', () => {
    it('should clear all handlers', () => {
      const handler1 = vi.fn()
      const handler2 = vi.fn()

      router.on('market:tick:BANKNIFTY', handler1)
      router.onAll(handler2)

      router.clear()

      router.route('market:tick:BANKNIFTY', { price: 45000 })

      expect(handler1).not.toHaveBeenCalled()
      expect(handler2).not.toHaveBeenCalled()
    })
  })
})
