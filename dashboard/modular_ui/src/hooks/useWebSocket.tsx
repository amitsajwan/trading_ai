import React, { createContext, useContext, useEffect, useRef, useCallback } from 'react'
import { useDispatch } from 'react-redux'
import { updateTick, updateIndicators, updateOHLC, updateOptionsChain, TickData } from '../store/slices/marketDataSlice'
import { updateDecision, updatePortfolio, addTrade, addOrUpdateSignal } from '../store/slices/tradingSlice'
import { addNotification } from '../store/slices/uiSlice'

interface WebSocketContextType {
  ws: WebSocket | null
  connected: boolean
  connect: () => void
  disconnect: () => void
  subscribe: (channels: string[]) => void
  unsubscribe: (channels: string[]) => void
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

// Redis WebSocket Gateway URL
const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8889/ws'

// Log the WebSocket URL for debugging (only in development)
if (import.meta.env.DEV) {
  console.log('WebSocket URL configured:', WS_URL)
  console.log('VITE_WS_URL from env:', import.meta.env.VITE_WS_URL)
}

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const dispatch = useDispatch()
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = React.useState(false)
  const subscribedChannels = useRef<Set<string>>(new Set())

  // Reconnect / heartbeat state
  const reconnectAttempts = useRef(0)
  const lastPong = useRef<number>(Date.now())
  const maxReconnectAttempts = 10
  const backoff = (attempt: number) => Math.min(30_000, 1000 * Math.pow(2, attempt))
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  
  // Debouncing refs for rapid updates
  const tickUpdateQueue = useRef<TickData[]>([])
  const tickUpdateTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const scheduleReconnect = useCallback(() => {
    if (reconnectAttempts.current >= maxReconnectAttempts) {
      dispatch(addNotification({
        type: 'error',
        title: 'Reconnect Failed',
        message: 'Unable to reconnect to real-time services'
      }))
      return
    }
    reconnectAttempts.current += 1
    const delay = backoff(reconnectAttempts.current)
    console.log(`Scheduling reconnect in ${delay}ms (attempt ${reconnectAttempts.current})`)
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    reconnectTimeoutRef.current = setTimeout(() => {
      if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
        connect()
      }
    }, delay)
  }, [dispatch])

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  const subscribe = useCallback((channels: string[]) => {
    if (channels.length === 0) return
    
    channels.forEach(ch => subscribedChannels.current.add(ch))
    sendMessage({
      action: 'subscribe',
      channels: channels,
      requestId: `sub-${Date.now()}`
    })
  }, [sendMessage])

  const unsubscribe = useCallback((channels: string[]) => {
    if (channels.length === 0) return
    
    channels.forEach(ch => subscribedChannels.current.delete(ch))
    sendMessage({
      action: 'unsubscribe',
      channels: channels,
      requestId: `unsub-${Date.now()}`
    })
  }, [sendMessage])

  const resubscribe = useCallback(() => {
    if (subscribedChannels.current.size > 0) {
      subscribe(Array.from(subscribedChannels.current))
    }
  }, [subscribe])

  const connect = useCallback(() => {
    if (!WS_URL) {
      console.info('WebSocket disabled: set VITE_WS_URL to enable real-time connections')
      return
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return
    }

    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close()
    }

    try {
      // Ensure we're using the correct URL (port 8889, not 8888)
      const wsUrl = WS_URL || 'ws://localhost:8889/ws'
      if (import.meta.env.DEV) {
        console.log('Connecting to WebSocket:', wsUrl)
      }
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        reconnectAttempts.current = 0
        console.log('WebSocket connected to Redis Gateway')
        setConnected(true)
        dispatch(addNotification({
          type: 'success',
          title: 'Connected',
          message: 'Real-time data connection established'
        }))

        // Resubscribe to all previous channels
        resubscribe()

        // Start ping interval (every 20 seconds)
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current)
        }
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            sendMessage({ action: 'ping', requestId: `ping-${Date.now()}` })
          }
        }, 20_000)
      }

      ws.onclose = (event) => {
        console.log('WebSocket disconnected', event.code, event.reason)
        setConnected(false)
        
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current)
          pingIntervalRef.current = null
        }

        // Only reconnect if not a normal closure
        if (event.code !== 1000) {
          dispatch(addNotification({
            type: 'warning',
            title: 'Disconnected',
            message: 'Real-time data connection lost'
          }))
          scheduleReconnect()
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        console.error('WebSocket URL attempted:', wsUrl)
        console.error('Expected URL: ws://localhost:8889/ws')
        if (wsUrl.includes('8888')) {
          console.error('⚠️ ERROR: WebSocket URL is using port 8888 instead of 8889!')
          console.error('Please check VITE_WS_URL environment variable or restart Vite dev server')
        }
        dispatch(addNotification({
          type: 'error',
          title: 'Connection Error',
          message: `WebSocket connection failed. Check console for details. URL: ${wsUrl}`
        }))
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          
          // Handle different message types from gateway
          switch (message.type) {
            case 'connected':
              console.log('Gateway connected:', message)
              break

            case 'pong':
              lastPong.current = Date.now()
              break

            case 'subscribed':
              console.log('Subscribed to channels:', message.channels)
              if (message.errors && message.errors.length > 0) {
                console.warn('Subscription errors:', message.errors)
              }
              break

            case 'unsubscribed':
              console.log('Unsubscribed from channels:', message.channels)
              break

            case 'data':
              // Handle real-time data based on channel
              const channel = message.channel || ''
              const data = message.data || {}

              // Map channels to Redux actions
              if (channel.startsWith('market:tick:') || channel === 'market:tick') {
                // Market tick update - debounce rapid updates to prevent flickering
                if (import.meta.env.DEV) {
                  console.log('📊 WebSocket tick received:', channel, data)
                }
                
                // Queue the update
                tickUpdateQueue.current.push(data)
                
                // Clear existing timeout
                if (tickUpdateTimeoutRef.current) {
                  clearTimeout(tickUpdateTimeoutRef.current)
                }
                
                // Debounce: process updates every 100ms (10 updates per second max)
                tickUpdateTimeoutRef.current = setTimeout(() => {
                  if (tickUpdateQueue.current.length > 0) {
                    // Process the most recent tick
                    const latestTick = tickUpdateQueue.current[tickUpdateQueue.current.length - 1]
                    dispatch(updateTick(latestTick))
                    tickUpdateQueue.current = []
                  }
                }, 100)
              } else if (channel.startsWith('engine:signal:') || channel === 'engine:signal') {
                // Trading signal update - update signal list and show notification
                dispatch(addOrUpdateSignal({
                  signal_id: data.signal_id || data.condition_id,
                  condition_id: data.condition_id,
                  instrument: data.instrument,
                  action: data.action || data.signal,
                  status: data.status || data.state || 'pending',
                  confidence: data.confidence || data.confidence_pct || 0.0,
                  timestamp: data.timestamp || data.created_at || new Date().toISOString(),
                  reasoning: data.reasoning || data.reason || '',
                  operator: data.operator,
                  threshold: data.threshold,
                  // include metadata if present
                  metadata: data.metadata || data.options_strategy_summary || undefined
                }))

                dispatch(addNotification({
                  type: 'info',
                  title: 'Signal Update',
                  message: `Signal: ${data.action || data.signal || 'N/A'} (${(Number(data.confidence ?? 0)).toFixed(1)}% confidence)`
                }))
              } else if (channel.startsWith('engine:decision:')) {
                // Agent decision update
                dispatch(updateDecision(data))
              } else if (channel === 'engine:decision') {
                // General decision
                dispatch(updateDecision(data))
              } else if (channel.startsWith('indicators:')) {
                // Technical indicators update
                if (import.meta.env.DEV) {
                  console.log('📊 WebSocket indicator update:', channel, data)
                }
                // Extract instrument from channel (e.g., "indicators:BANKNIFTY" -> "BANKNIFTY")
                const instrument = channel.split(':').slice(1).join(':') || 'BANKNIFTY'
                dispatch(updateIndicators({
                  ...data,
                  instrument,
                  timestamp: data.timestamp || new Date().toISOString(),
                }))
              } else if (channel.startsWith('market:ohlc:') || channel === 'market:ohlc') {
                // OHLC candle update
                if (import.meta.env.DEV) {
                  console.log('📊 WebSocket OHLC update:', channel, data)
                }
                dispatch(updateOHLC(data))
              } else if (channel.startsWith('market:options:') || channel === 'market:options') {
                // Options chain update
                if (import.meta.env.DEV) {
                  console.log('📊 WebSocket options chain update:', channel, data)
                }
                dispatch(updateOptionsChain(data))
              }

              // Handle portfolio and trade updates if present in data
              if (data.portfolio) {
                dispatch(updatePortfolio(data.portfolio))
              }
              if (data.trade || data.trade_executed) {
                const trade = data.trade || data.trade_executed
                dispatch(addTrade(trade))
                dispatch(addNotification({
                  type: 'info',
                  title: 'Trade Executed',
                  message: `Trade ${trade.id || 'N/A'} executed for ${trade.instrument || 'N/A'}`
                }))
              }
              break

            case 'error':
              console.error('Gateway error:', message.error)
              dispatch(addNotification({
                type: 'error',
                title: 'Gateway Error',
                message: message.error || 'Unknown error'
              }))
              break

            default:
              console.log('Unknown message type:', message.type, message)
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error, event.data)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      scheduleReconnect()
    }
  }, [dispatch, WS_URL, scheduleReconnect, resubscribe, sendMessage])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
    if (tickUpdateTimeoutRef.current) {
      clearTimeout(tickUpdateTimeoutRef.current)
      tickUpdateTimeoutRef.current = null
    }
    // Process any queued ticks before disconnecting
    if (tickUpdateQueue.current.length > 0) {
      const latestTick = tickUpdateQueue.current[tickUpdateQueue.current.length - 1]
      dispatch(updateTick(latestTick))
      tickUpdateQueue.current = []
    }
    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect')
      wsRef.current = null
      setConnected(false)
    }
  }, [dispatch])

  useEffect(() => {
    // Auto-connect on mount
    connect()

    // Cleanup on unmount
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  // Heartbeat and reconnect management
  useEffect(() => {
    const interval = setInterval(() => {
      try {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          // Check if pong received recently (within 60s)
          if (Date.now() - lastPong.current > 60_000) {
            console.warn('No pong received, reconnecting...')
            disconnect()
            scheduleReconnect()
          }
        } else if (!connected && wsRef.current?.readyState === WebSocket.CLOSED) {
          // Attempt to reconnect if closed
          scheduleReconnect()
        }
      } catch (e) {
        console.error('Heartbeat check failed', e)
      }
    }, 20_000)

    return () => clearInterval(interval)
  }, [connected, connect, disconnect, scheduleReconnect])

  // Auto-subscribe to common channels on connect
  useEffect(() => {
    if (connected) {
      // Subscribe to common channels
      subscribe([
        'market:tick:*',
        'engine:signal:*',
        'engine:decision:*',
        'indicators:*'
      ])
    }
  }, [connected, subscribe])

  return (
    <WebSocketContext.Provider value={{ 
      ws: wsRef.current, 
      connected, 
      connect, 
      disconnect,
      subscribe,
      unsubscribe
    }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export const useWebSocket = () => {
  const context = useContext(WebSocketContext)
  if (context === undefined) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}
