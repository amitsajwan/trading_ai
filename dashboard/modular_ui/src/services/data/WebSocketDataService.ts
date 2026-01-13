/**
 * WebSocketDataService - Wraps WebSocket subscriptions
 * 
 * Manages WebSocket subscriptions and callbacks.
 * Integrates with existing useWebSocket hook via subscription functions.
 * 
 * Note: This service is used by HybridDataService, which will be a React hook
 * that can access the useWebSocket context.
 */

import { SubscribeOptions } from './types'

/**
 * WebSocket subscription manager
 * 
 * This service manages WS subscriptions and routes messages to callbacks.
 * It's designed to work with the existing useWebSocket hook via subscription functions.
 */
export class WebSocketDataService {
  private subscriptions: Map<string, Set<(data: any) => void>> = new Map()
  private subscribeFn?: (channels: string[]) => void
  private unsubscribeFn?: (channels: string[]) => void
  private isConnected: boolean = false

  /**
   * Initialize with subscription functions from useWebSocket
   */
  initialize(options: {
    subscribe: (channels: string[]) => void
    unsubscribe: (channels: string[]) => void
    isConnected: () => boolean
    onMessage: (channel: string, data: any) => void
  }) {
    this.subscribeFn = options.subscribe
    this.unsubscribeFn = options.unsubscribe
    this.isConnected = options.isConnected()

    // Setup message handler (called by HybridDataService)
    this._onMessage = options.onMessage
  }

  private _onMessage?: (channel: string, data: any) => void

  /**
   * Subscribe to a WebSocket channel
   * @param channel WebSocket channel (e.g., "market:tick:BANKNIFTY")
   * @param callback Function to call when data arrives
   */
  subscribe<T = any>(channel: string, callback: (data: T) => void): () => void {
    const isNewChannel = !this.subscriptions.has(channel)
    
    // Add callback to subscription map
    if (!this.subscriptions.has(channel)) {
      this.subscriptions.set(channel, new Set())
    }
    this.subscriptions.get(channel)!.add(callback)

    // Only subscribe to channel if it's new and WS is connected
    if (isNewChannel && this.isConnected && this.subscribeFn) {
      this.subscribeFn([channel])
    }

    // Return unsubscribe function
    return () => {
      this.unsubscribe(channel, callback)
    }
  }

  /**
   * Unsubscribe from a channel
   */
  private unsubscribe<T = any>(channel: string, callback: (data: T) => void): void {
    const callbacks = this.subscriptions.get(channel)
    if (callbacks) {
      callbacks.delete(callback)
      
      // If no more callbacks, unsubscribe from channel
      if (callbacks.size === 0) {
        this.subscriptions.delete(channel)
        if (this.unsubscribeFn) {
          this.unsubscribeFn([channel])
        }
      }
    }
  }

  /**
   * Handle incoming WebSocket message
   * Called by HybridDataService when WS message arrives
   */
  handleMessage(channel: string, data: any): void {
    const callbacks = this.subscriptions.get(channel)
    if (callbacks) {
      callbacks.forEach((callback) => {
        try {
          callback(data)
        } catch (error) {
          console.error(`Error in WebSocket callback for channel ${channel}:`, error)
        }
      })
    }

    // Also try wildcard subscriptions (e.g., "market:tick:*")
    // Match channel patterns
    this.subscriptions.forEach((callbacks, subChannel) => {
      if (this.matchChannel(channel, subChannel)) {
        callbacks.forEach((callback) => {
          try {
            callback(data)
          } catch (error) {
            console.error(`Error in WebSocket callback for channel ${subChannel}:`, error)
          }
        })
      }
    })
  }

  /**
   * Check if channel matches pattern (supports wildcards)
   * e.g., "market:tick:BANKNIFTY" matches "market:tick:*"
   */
  private matchChannel(channel: string, pattern: string): boolean {
    if (pattern === channel) {
      return true
    }

    // Handle wildcard patterns
    if (pattern.includes('*')) {
      const regex = new RegExp('^' + pattern.replace(/\*/g, '.*') + '$')
      return regex.test(channel)
    }

    return false
  }

  /**
   * Update connection status
   */
  setConnected(connected: boolean): void {
    this.isConnected = connected

    // If just connected, resubscribe to all channels
    if (connected && this.subscribeFn && this.subscriptions.size > 0) {
      const channels = Array.from(this.subscriptions.keys())
      this.subscribeFn(channels)
    }
  }

  /**
   * Get all subscribed channels
   */
  getSubscribedChannels(): string[] {
    return Array.from(this.subscriptions.keys())
  }

  /**
   * Clear all subscriptions
   */
  clear(): void {
    if (this.unsubscribeFn && this.subscriptions.size > 0) {
      const channels = Array.from(this.subscriptions.keys())
      this.unsubscribeFn(channels)
    }
    this.subscriptions.clear()
  }
}
