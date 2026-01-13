import React, { createContext, useContext, useEffect, useRef, useCallback } from 'react'
import { useDispatch } from 'react-redux'
import { updateTick, updateIndicators, updateOHLC, updateOptionsChain, TickData } from '../store/slices/marketDataSlice'
import { updateDecision, updatePortfolio, addTrade, addOrUpdateSignal, updateAgentResponse, updateOrchestratorDecision } from '../store/slices/tradingSlice'
import { addNotification } from '../store/slices/uiSlice'
import { messageRouter } from '../services/data/WebSocketMessageRouter'

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
  console.log('WS_URL truthy:', !!WS_URL)
  console.log('WS_URL value:', WS_URL)
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

  // Use a ref to store the latest connect function to avoid circular dependency
  const connectRef = useRef<() => void>()
  
  const scheduleReconnect = useCallback(() => {
    if (reconnectAttempts.current >= maxReconnectAttempts) {
      dispatch(addNotification({
        type: 'error',
        title: 'Reconnect Failed',
        message: 'Unable to reconnect to real-time services after multiple attempts'
      }))
      return
    }
    reconnectAttempts.current += 1
    const delay = backoff(reconnectAttempts.current)
    console.log(`[WebSocket] Scheduling reconnect in ${delay}ms (attempt ${reconnectAttempts.current}/${maxReconnectAttempts})`)
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    reconnectTimeoutRef.current = setTimeout(() => {
      // Check if we still need to reconnect (might have connected in the meantime)
      if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED || wsRef.current.readyState === WebSocket.CONNECTING) {
        console.log(`[WebSocket] Attempting reconnect (attempt ${reconnectAttempts.current})`)
        // Use ref to get latest connect function
        if (connectRef.current) {
          connectRef.current()
        }
      } else {
        console.log('[WebSocket] Reconnect cancelled - connection already established')
        reconnectAttempts.current = 0 // Reset if already connected
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
      console.log('🔌 Connecting to WebSocket:', wsUrl)

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      console.log('🔌 WebSocket instance created:', ws)

      // Handle WebSocket connection opened
      ws.onopen = () => {
        console.log('🔌 WebSocket connection OPENED successfully')
        console.log('✅ WebSocket connection opened')
        setConnected(true)
        reconnectAttempts.current = 0 // Reset reconnect attempts on successful connection
        lastPong.current = Date.now() // Initialize lastPong timestamp
        
        // Start ping/heartbeat interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current)
        }
        pingIntervalRef.current = setInterval(() => {
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            sendMessage({
              action: 'ping',
              requestId: `ping-${Date.now()}`
            })
          }
        }, 30_000) // Ping every 30 seconds
        
        // Resubscribe to previously subscribed channels
        resubscribe()
      }

      // Handle WebSocket connection closed
      ws.onclose = (event) => {
        console.log('🔌 WebSocket connection CLOSED:', event.code, event.reason, event.wasClean)
        setConnected(false)
        
        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current)
          pingIntervalRef.current = null
        }
        
        // Only attempt reconnect if it wasn't a clean close by the client
        if (event.code !== 1000) {
          console.log('WebSocket closed unexpectedly, scheduling reconnect...')
          scheduleReconnect()
        }
      }

      // Handle WebSocket errors
      ws.onerror = (error) => {
        console.error('🔌 WebSocket ERROR:', error)
        setConnected(false)
        // Note: onclose will be called after onerror, so we don't schedule reconnect here
        // to avoid double reconnection attempts
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          
          // Handle different message types from gateway
          switch (message.type) {
            case 'connected':
              // Gateway confirmation message (sent after WebSocket opens)
              // Connection state is already set in onopen, but we can use this to confirm
              console.log('Gateway confirmed connection:', message)
              // Ensure we're marked as connected (redundant but safe)
              if (!connected) {
                setConnected(true)
              }
              break

            case 'pong':
              lastPong.current = Date.now()
              if (import.meta.env.DEV) {
                console.log('Pong received')
              }
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


              // Route to message router for new data services (HybridDataService)
              messageRouter.route(channel, data)

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
                    const rawTick = tickUpdateQueue.current[tickUpdateQueue.current.length - 1]
                    console.log('📊 Processing tick update:', rawTick)

                    // Transform raw tick data to match TickData interface
                    const transformedTick = {
                      instrument: rawTick.instrument || 'NIFTY BANK',
                      last_price: rawTick.price || rawTick.last_price || rawTick.ltp,
                      timestamp: rawTick.ts || rawTick.timestamp || new Date().toISOString(),
                      volume: rawTick.volume,
                      oi: rawTick.oi
                    }

                    dispatch(updateTick(transformedTick))
                    tickUpdateQueue.current = []
                  }
                }, 100)
                return // Prevent further processing of tick messages
              } else if (channel.startsWith('engine:signal:') || channel === 'engine:signal' ||
                         channel.startsWith('signals:') || channel === 'signals' ||
                         channel.startsWith('trading:signals:') || channel === 'trading:signals' ||
                         channel.startsWith('market:signals:') || channel === 'market:signals') {
                // Trading signal update - update signal list and show notification
                console.log('📊 WebSocket signal received:', channel, data)
                // Normalize signal data for UI compatibility
                let normalizedSignal = data.action || data.signal || 'HOLD'

                // Map OPTIONS strategy actions to BUY/SELL/HOLD for UI display
                if (data.strategy_type === 'OPTIONS') {
                  if (normalizedSignal.includes('BUY') || normalizedSignal.includes('CALL') || normalizedSignal.includes('PUT')) {
                    normalizedSignal = normalizedSignal.startsWith('SELL') ? 'SELL' : 'BUY'
                  } else {
                    normalizedSignal = 'HOLD'
                  }
                }

                const signalData = {
                  signal_id: data.signal_id || data.condition_id,
                  condition_id: data.condition_id,
                  instrument: data.instrument,
                  action: data.action || data.signal, // Keep original action for details
                  signal: normalizedSignal, // Add normalized signal for UI
                  status: data.status || data.state || 'pending',
                  confidence: data.confidence || data.confidence_pct || 0.0,
                  timestamp: data.timestamp || data.created_at || new Date().toISOString(),
                  reasoning: data.reasoning || data.reason || '',
                  operator: data.operator,
                  threshold: data.threshold,
                  strategy_type: data.strategy_type,
                  // include metadata if present
                  metadata: data.metadata || data.options_strategy_summary || undefined
                }
                console.log('📊 Processing signal for Redux:', signalData)
                dispatch(addOrUpdateSignal(signalData))

                dispatch(addNotification({
                  type: 'info',
                  title: 'Signal Update',
                  message: `Signal: ${data.action || data.signal || 'N/A'} (${(Number(data.confidence ?? 0)).toFixed(1)}% confidence)`
                }))
                return // Prevent further processing of signal messages
              } else if (channel.startsWith('engine:decision:') || channel === 'engine:decision') {
                // Agent decision update (consolidated handler)
                console.log('📊 WebSocket decision received:', channel, data)
                dispatch(updateDecision(data))

                // Individual agent decision update (from API service)
                console.log('🤖 WebSocket agent decision received:', channel, data)
                dispatch(updateAgentResponse({
                  agent: data.agent_name || data.agent || 'unknown',
                  decision: data.direction || data.decision || data.signal || 'HOLD',
                  confidence: data.confidence || 0,
                  timestamp: data.timestamp || new Date().toISOString(),
                  details: {
                    reasoning: data.signal || 'Agent analysis completed',
                    direction: data.direction
                  }
                }))

                // Publish orchestrator decision to orchestrator decisions store
                dispatch(updateOrchestratorDecision({
                  decision_id: `decision_${Date.now()}`,
                  instrument: data.instrument || 'BANKNIFTY',
                  final_decision: data.final_decision,
                  confidence: data.confidence,
                  reasoning: data.reasoning,
                  agent_responses: data.agent_responses || [],
                  signal_created: data.signal_created || false,
                  signal_id: data.signal_id,
                  timestamp: data.timestamp
                }))

                return // Prevent further processing of decision messages
              } else if (channel.startsWith('engine:agent:') || channel === 'engine:agent') {
                // Detailed agent analysis update
                console.log('🤖 WebSocket detailed agent analysis received:', channel, data)

                // Update agent status with rich data
                dispatch(updateAgentStatus({
                  name: data.agent_name,
                  status: 'active',
                  signal: data.decision,
                  confidence: data.confidence,
                  last_update: data.timestamp,
                  summary: data.details,
                  technical_indicators: data.technical_indicators,
                  reasoning: data.reasoning
                }))

                // Also update agent response with detailed information
                dispatch(updateAgentResponse({
                  agent: data.agent_name,
                  decision: data.decision,
                  confidence: data.confidence,
                  timestamp: data.timestamp,
                  details: {
                    reasoning: data.reasoning || 'Analysis completed',
                    technical_indicators: data.technical_indicators,
                    cycle_info: data.cycle_info
                  }
                }))

                return // Prevent further processing of agent messages
              } else if (channel.startsWith('indicators:')) {
                // Technical indicators update
                console.log('📊 WebSocket indicator update:', channel, {
                  atr_14: data.atr_14,
                  atr_20: data.atr_20,
                  rsi_14: data.rsi_14,
                  macd_value: data.macd_value,
                  adx_14: data.adx_14,
                  has_atr_14: 'atr_14' in data,
                  data_keys: Object.keys(data).slice(0, 15) // Limit to first 15 keys
                })

                // Extract instrument and timeframe from channel (e.g., "indicators:BANKNIFTY:1min" -> "BANKNIFTY", "1min")
                const parts = channel.split(':')
                const instrument = parts[1] || 'BANKNIFTY'
                const timeframe = parts[2] || data.timeframe || '1min' // Support both channel-based and data-based timeframe

                console.log('🚀 Dispatching updateIndicators for', instrument, timeframe, 'ATR_14:', data.atr_14)
                dispatch(updateIndicators({
                  ...data,
                  instrument,
                  timeframe,
                  timestamp: data.timestamp || new Date().toISOString(),
                }))
                console.log('✅ updateIndicators dispatched - ATR should now be in Redux')
                return
              } else if (channel.startsWith('market:ohlc:') || channel === 'market:ohlc') {
                // OHLC candle update
                if (import.meta.env.DEV) {
                  console.log('📊 WebSocket OHLC update:', channel, data)
                }
                // Extract instrument and timeframe from channel (e.g., "market:ohlc:BANKNIFTY:5min" -> "BANKNIFTY", "5min")
                const parts = channel.split(':')
                const instrument = parts[2] || data.instrument || 'BANKNIFTY'
                const timeframe = parts[3] || data.timeframe || '1min'

                dispatch(updateOHLC({
                  ...data,
                  instrument,
                  timeframe
                }))
                return // Prevent further processing of OHLC messages
              } else if (channel.startsWith('market:options:') || channel === 'market:options') {
                // Options chain update
                if (import.meta.env.DEV) {
                  console.log('📊 WebSocket options chain update:', channel, data)
                }
                dispatch(updateOptionsChain(data))
                return // Prevent further processing of options messages
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
              } else {
                // Unrecognized channel - log for debugging
                console.log('📊 WebSocket unrecognized channel:', channel, data)
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
      setConnected(false)
      scheduleReconnect()
    }
    // Note: resubscribe and sendMessage are stable callbacks
  }, [dispatch, scheduleReconnect, resubscribe, sendMessage])

  // Update connectRef whenever connect changes
  useEffect(() => {
    connectRef.current = connect
  }, [connect])

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
      // Subscribe to common channels (reduced to stay under limit)
      subscribe([
        'market:tick:*',
        'engine:signal',
        'engine:signal:*',
        'engine:decision',
        'engine:decision:*',
        'engine:agent',
        'engine:agent:*',
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
