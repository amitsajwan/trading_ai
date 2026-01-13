/**
 * WebSocketMessageRouter - Routes WebSocket messages to registered handlers
 * 
 * This bridges the existing useWebSocket message handling with our new data services.
 * Allows multiple systems (Redux, HybridDataService) to handle WS messages.
 */

type MessageHandler = (channel: string, data: any) => void

/**
 * Global message router for WebSocket messages
 * 
 * Usage:
 * - Register handlers for channels
 * - When WS messages arrive, router calls all registered handlers
 */
export class WebSocketMessageRouter {
  private handlers: Map<string, Set<MessageHandler>> = new Map()
  private wildcardHandlers: Set<MessageHandler> = new Set()

  /**
   * Register a handler for a specific channel
   */
  on(channel: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(channel)) {
      this.handlers.set(channel, new Set())
    }
    this.handlers.get(channel)!.add(handler)

    // Return unsubscribe function
    return () => {
      this.off(channel, handler)
    }
  }

  /**
   * Register a handler for all channels (wildcard)
   */
  onAll(handler: MessageHandler): () => void {
    this.wildcardHandlers.add(handler)

    // Return unsubscribe function
    return () => {
      this.wildcardHandlers.delete(handler)
    }
  }

  /**
   * Unregister a handler
   */
  off(channel: string, handler: MessageHandler): void {
    const handlers = this.handlers.get(channel)
    if (handlers) {
      handlers.delete(handler)
      if (handlers.size === 0) {
        this.handlers.delete(channel)
      }
    }
  }

  /**
   * Route a message to registered handlers
   */
  route(channel: string, data: any): void {
    // Call specific channel handlers
    const handlers = this.handlers.get(channel)
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(channel, data)
        } catch (error) {
          console.error(`Error in message handler for channel ${channel}:`, error)
        }
      })
    }

    // Call wildcard handlers
    this.wildcardHandlers.forEach((handler) => {
      try {
        handler(channel, data)
      } catch (error) {
        console.error(`Error in wildcard message handler:`, error)
      }
    })

    // Handle wildcard pattern matching (e.g., "market:tick:*" matches "market:tick:BANKNIFTY")
    this.handlers.forEach((handlers, pattern) => {
      if (pattern.includes('*') && this.matchChannel(channel, pattern)) {
        handlers.forEach((handler) => {
          try {
            handler(channel, data)
          } catch (error) {
            console.error(`Error in wildcard pattern handler for ${pattern}:`, error)
          }
        })
      }
    })
  }

  /**
   * Check if channel matches pattern (supports wildcards)
   */
  private matchChannel(channel: string, pattern: string): boolean {
    if (pattern === channel) {
      return true
    }
    if (pattern.includes('*')) {
      const regex = new RegExp('^' + pattern.replace(/\*/g, '.*') + '$')
      return regex.test(channel)
    }
    return false
  }

  /**
   * Clear all handlers
   */
  clear(): void {
    this.handlers.clear()
    this.wildcardHandlers.clear()
  }
}

// Singleton instance
export const messageRouter = new WebSocketMessageRouter()
