import React, { useMemo } from 'react'
import { useSelector, useDispatch, shallowEqual } from 'react-redux'
import { TrendingUp, TrendingDown, Minus, Target, AlertTriangle, BarChart3, Play } from 'lucide-react'
import { RootState } from '../../store'
import { formatTimestampForDisplay } from '../../utils/dateUtils'
import { executeSignalWhenReady } from '../../store/slices/tradingSlice'

export const CurrentSignalWidget: React.FC = React.memo(() => {
  // Use selective selectors to prevent unnecessary re-renders
  const dispatch = useDispatch()
  const latestDecision = useSelector((state: RootState) => state.trading.latestDecision, shallowEqual)
  const optionsStrategy = useSelector((state: RootState) => state.trading.optionsStrategy, shallowEqual)
  const loading = useSelector((state: RootState) => state.trading.loading.decision)
  const signals = useSelector((state: RootState) => state.trading.signals, shallowEqual)

  // Find a relevant active signal (prefer pending, then most recent)
  // Memoize to prevent recalculation on every render
  const activeSignal = useMemo(() => {
    console.log('📊 CurrentSignalWidget: signals in Redux:', signals?.length || 0, signals)
    console.log('📊 CurrentSignalWidget: latestDecision:', latestDecision)

    if (!signals || signals.length === 0) {
      console.log('📊 CurrentSignalWidget: No signals in Redux')
      return null
    }

    // First try to find signals matching latestDecision instrument
    if (latestDecision?.instrument) {
      const matchingSignal = signals.find(s => s.instrument === latestDecision.instrument && (s.status === 'pending' || s.status === 'triggered'))
        || signals.find(s => s.instrument === latestDecision.instrument)
      if (matchingSignal) {
        console.log('📊 CurrentSignalWidget: Found matching signal:', matchingSignal)
        return matchingSignal
      }
    }

    // Fallback: show most recent pending/triggered signal
    const fallbackSignal = signals.find(s => s.status === 'pending' || s.status === 'triggered')
        || signals[0] // Most recent signal
    console.log('📊 CurrentSignalWidget: Using fallback signal:', fallbackSignal)
    return fallbackSignal
  }, [signals, latestDecision?.instrument])

  // Determine the signal to display (prefer latestDecision, fallback to activeSignal)
  const displaySignal = latestDecision?.signal || activeSignal?.signal || 'HOLD'
  const displayConfidence = latestDecision?.confidence || activeSignal?.confidence || 0
  const displayReasoning = latestDecision?.reasoning || activeSignal?.reasoning || ''
  const displayInstrument = latestDecision?.instrument || activeSignal?.instrument || 'BANKNIFTY'
  const displayEntryPrice = latestDecision?.entry_price || activeSignal?.entry_price
  const displayStopLoss = latestDecision?.stop_loss || activeSignal?.stop_loss
  const displayTakeProfit = latestDecision?.take_profit || activeSignal?.take_profit

  // Generate options strategy details using LLM-enhanced strike price calculation
  const getOptionsStrategyDetails = async (signal: string, instrument: string) => {
    if (signal === 'IRON_CONDOR') {
      // Use LLM-generated strike prices instead of hard-coded values
      const llmGeneratedStrikes = await generateLLMStrikePrices(signal, instrument)

      return {
        strategy: 'IRON_CONDOR',
        description: 'Neutral options strategy collecting premium in low volatility market conditions',
        legs: llmGeneratedStrikes.legs,
        maxProfit: llmGeneratedStrikes.maxProfit,
        maxLoss: llmGeneratedStrikes.maxLoss,
        breakeven: llmGeneratedStrikes.breakeven,
        rationale: llmGeneratedStrikes.rationale
      }
    }
    return null
  }

  // LLM-powered strike price generation with real API call
  const generateLLMStrikePrices = async (strategy: string, instrument: string) => {
    try {
      const response = await fetch('/api/generate-strikes', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          strategy,
          instrument
          // Backend now fetches REAL market data automatically
        })
      })

      if (response.ok) {
        const data = await response.json()
        console.log('LLM Generated Strikes:', data)
        return data
      } else {
        console.error('LLM API failed, using fallback')
        return getFallbackStrikes(strategy, instrument)
      }
    } catch (error) {
      console.error('LLM API error:', error)
      return getFallbackStrikes(strategy, instrument)
    }
  }

  // Fallback strike generation when LLM is unavailable
  const getFallbackStrikes = (strategy: string, instrument: string) => {
    const spotPrice = 59080 // Use current market price
    const rangeWidth = Math.round(spotPrice * 0.05)

    return {
      legs: [
        { action: 'SELL', type: 'PUT', strike: spotPrice - rangeWidth, quantity: 1, premium: 150, order: 1, purpose: 'Premium collection - bear protection' },
        { action: 'SELL', type: 'CALL', strike: spotPrice + Math.round(rangeWidth * 0.3), quantity: 1, premium: 140, order: 2, purpose: 'Premium collection - bull protection' },
        { action: 'BUY', type: 'PUT', strike: spotPrice - Math.round(rangeWidth * 0.3), quantity: 1, premium: 50, order: 3, purpose: 'Protection - limits downside risk' },
        { action: 'BUY', type: 'CALL', strike: spotPrice + rangeWidth, quantity: 1, premium: 45, order: 4, purpose: 'Protection - limits upside risk' }
      ],
      maxProfit: `₹${Math.round(rangeWidth * 0.3 * 100)}`,
      maxLoss: `₹${rangeWidth * 100}`,
      breakeven: `${spotPrice - rangeWidth - Math.round(rangeWidth * 0.3)} - ${spotPrice + rangeWidth + Math.round(rangeWidth * 0.3)}`,
      rationale: 'Fallback algorithmic strike selection when LLM is unavailable.'
    }
  }

  // State for LLM-generated options details
  const [optionsDetails, setOptionsDetails] = React.useState<any>(null)
  const [loadingStrikes, setLoadingStrikes] = React.useState(false)

  // Load options details when signal changes
  React.useEffect(() => {
    const loadOptionsDetails = async () => {
      if (displaySignal === 'IRON_CONDOR') {
        setLoadingStrikes(true)
        try {
          const details = await getOptionsStrategyDetails(displaySignal, displayInstrument)
          setOptionsDetails(details)
        } catch (error) {
          console.error('Error loading options details:', error)
          setOptionsDetails(null)
        } finally {
          setLoadingStrikes(false)
        }
      } else {
        setOptionsDetails(null)
      }
    }

    loadOptionsDetails()
  }, [displaySignal, displayInstrument])

  // If we have an options strategy, show a summary of it (or fallback to active signal metadata)
  let summary = null

  if (optionsStrategy?.available) {
    // Use the full options strategy from Redux
    summary = optionsStrategy
  } else if (activeSignal?.metadata?.options_strategy_summary) {
    // Use the options strategy summary from signal metadata
    summary = activeSignal.metadata.options_strategy_summary
  }

  if (summary) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Current Strategy
          </h3>
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Live
            </span>
          </div>
        </div>

        {/* Options Strategy Summary */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-200 mb-3">
            <BarChart3 className="w-6 h-6" />
            <span className="text-xl font-bold uppercase">
              {summary.strategy_type.replace(/_/g, ' ')}
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            {summary.confidence.toFixed(1)}%
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs mx-auto">
            Multi-leg options strategy with {summary.legs_count || 'multiple'} legs
          </p>
        </div>

        {/* Quick Risk Summary */}
        <div className="space-y-3">
          <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-600">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Max Profit
            </span>
            <span className="text-sm font-semibold text-green-600 dark:text-green-400">
              ₹{(summary.max_profit || 0).toLocaleString('en-IN')}
            </span>
          </div>

          <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-600">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Max Loss
            </span>
            <span className="text-sm font-semibold text-red-600 dark:text-red-400">
              ₹{(summary.max_loss || 0).toLocaleString('en-IN')}
            </span>
          </div>

          <div className="flex justify-between items-center py-2">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Risk/Reward
            </span>
            <span className="text-sm font-semibold text-gray-900 dark:text-white">
              1:{((summary.max_profit || 1) / (summary.max_loss || 1)).toFixed(1)}
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600 dark:text-gray-400">
              {activeSignal.instrument}
            </span>
            <span className="text-gray-500 dark:text-gray-400">
              {formatTimestampForDisplay(activeSignal.timestamp)}
            </span>
          </div>
        </div>
      </div>
    )
  }

  // Original signal display logic
  if (loading.decision) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
          </div>
        </div>
      </div>
    )
  }

  if (!activeSignal) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Target className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No trading signals available</p>
          <p className="text-sm mt-1">AI agents are analyzing market conditions</p>
        </div>
      </div>
    )
  }

  const getSignalColor = (signal: string) => {
    switch (signal.toUpperCase()) {
      case 'BUY': return 'text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-200'
      case 'SELL': return 'text-red-600 bg-red-100 dark:bg-red-900 dark:text-red-200'
      case 'HOLD': return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900 dark:text-yellow-200'
      default: return 'text-gray-600 bg-gray-100 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  const getSignalIcon = (signal: string) => {
    switch (signal.toUpperCase()) {
      case 'BUY': return <TrendingUp className="w-6 h-6" />
      case 'SELL': return <TrendingDown className="w-6 h-6" />
      case 'HOLD': return <Minus className="w-6 h-6" />
      default: return <AlertTriangle className="w-6 h-6" />
    }
  }

  const formatPrice = (price: number | undefined) => {
    return price ? `₹${price.toLocaleString('en-IN')}` : '--'
  }

  const getStatusBadge = (status?: string) => {
    switch ((status || '').toLowerCase()) {
      case 'pending': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-200">PENDING</span>
      case 'monitoring': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200">MONITORING</span>
      case 'triggered': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">TRIGGERED</span>
      case 'executed': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200">EXECUTED</span>
      case 'expired': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-gray-100 text-gray-700 dark:bg-gray-900 dark:text-gray-200">EXPIRED</span>
      case 'cancelled': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200">CANCELLED</span>
      default: return null
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Current Signal
        </h3>
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Live
          </span>
        </div>
      </div>

      {/* Signal Display */}
      <div className="text-center mb-6">
        <div className="flex items-center justify-center mb-3 space-x-3">
          <div className={`inline-flex items-center space-x-2 px-4 py-2 rounded-lg ${getSignalColor(displaySignal)}`}>
            {getSignalIcon(displaySignal)}
            <span className="text-xl font-bold uppercase">
              {displaySignal}
            </span>
          </div>
          {/* Status badge from active signal */}
          <div>
            {getStatusBadge(activeSignal?.status)}
          </div>
        </div>

        <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          {displayConfidence.toFixed(1)}%
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs mx-auto">
          {displayReasoning}
        </p>

        {/* If active signal includes options strategy summary, show a compact summary */}
        {activeSignal?.metadata?.options_strategy_summary && (
          <div className="mt-4 bg-gray-50 dark:bg-gray-900 p-3 rounded">
            <div className="text-xs text-gray-500">Options Strategy</div>
            <div className="mt-1 text-sm">
              <strong>{activeSignal.metadata.options_strategy_summary.strategy_type}</strong> • {activeSignal.metadata.options_strategy_summary.legs_count} legs • Max loss: ₹{Number(activeSignal.metadata.options_strategy_summary.max_loss || 0).toLocaleString('en-IN')} • Expiry: {activeSignal.metadata.options_strategy_summary.expiry}
            </div>
          </div>
        )}
      </div>

      {/* Trading Parameters */}
      <div className="space-y-3">
        <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-600">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            Entry Price
          </span>
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            {formatPrice(displayEntryPrice)}
          </span>
        </div>

        <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-600">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            Stop Loss
          </span>
          <span className="text-sm font-semibold text-red-600 dark:text-red-400">
            {formatPrice(displayStopLoss)}
          </span>
        </div>

        <div className="flex justify-between items-center py-2">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            Take Profit
          </span>
          <span className="text-sm font-semibold text-green-600 dark:text-green-400">
            {formatPrice(displayTakeProfit)}
          </span>
        </div>
      </div>

      {/* Execute Button */}
      {activeSignal && activeSignal.status === 'pending' && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
          <button
            onClick={() => dispatch(executeSignalWhenReady(activeSignal.signal_id || activeSignal.condition_id) as any)}
            className={`w-full flex items-center justify-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              activeSignal.parsed_conditions?.every((c: any) => c.current_value !== undefined &&
                (() => {
                  const { operator, threshold, current_value } = c
                  switch (operator) {
                    case '>': return current_value > threshold
                    case '<': return current_value < threshold
                    case '>=': return current_value >= threshold
                    case '<=': return current_value <= threshold
                    case '==':
                    case 'EQUALS': return current_value === threshold
                    case 'BETWEEN': return Array.isArray(threshold) && current_value >= threshold[0] && current_value <= threshold[1]
                    default: return false
                  }
                })()
              ) ? 'bg-green-600 hover:bg-green-700 text-white' : 'bg-blue-600 hover:bg-blue-700 text-white'
            }`}
            disabled={activeSignal.status !== 'pending'}
          >
            <Play className="w-4 h-4" />
            <span>
              {activeSignal.execution_mode === 'IMMEDIATE' ? 'Execute Now' : 'Execute When Ready'}
            </span>
          </button>
        </div>
      )}

      {/* Show conditions if available */}
      {activeSignal?.parsed_conditions && activeSignal.parsed_conditions.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
            Entry Conditions
          </h4>
          <div className="space-y-2">
            {activeSignal.parsed_conditions.map((condition: any, index: number) => {
              const { indicator, operator, threshold, current_value } = condition
              let status = 'waiting'
              let statusText = 'Waiting'
              let statusColor = 'text-yellow-600'
              let bgColor = 'bg-yellow-50 dark:bg-yellow-900/20'

              if (current_value !== undefined) {
                let met = false
                switch (operator) {
                  case '>':
                    met = current_value > threshold
                    break
                  case '<':
                    met = current_value < threshold
                    break
                  case '>=':
                    met = current_value >= threshold
                    break
                  case '<=':
                    met = current_value <= threshold
                    break
                  case '==':
                  case 'EQUALS':
                    met = current_value === threshold
                    break
                  case 'BETWEEN':
                    met = Array.isArray(threshold) && current_value >= threshold[0] && current_value <= threshold[1]
                    break
                  default:
                    met = false
                }

                if (met) {
                  status = 'met'
                  statusText = '✓ Met'
                  statusColor = 'text-green-600'
                  bgColor = 'bg-green-50 dark:bg-green-900/20'
                } else {
                  status = 'not_met'
                  statusText = '✗ Not met'
                  statusColor = 'text-red-600'
                  bgColor = 'bg-red-50 dark:bg-red-900/20'
                }
              }

              return (
                <div key={index} className={`text-xs ${bgColor} px-3 py-2 rounded-lg border`}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-gray-900 dark:text-white">
                        {indicator.replace('_', ' ').toUpperCase()}
                      </span>
                      <span className={`font-semibold ${statusColor}`}>
                        {statusText}
                      </span>
                    </div>
                    <span className="text-gray-500">
                      {operator === 'BETWEEN' && Array.isArray(threshold)
                        ? `${threshold[0]} - ${threshold[1]}`
                        : `${operator} ${threshold}`
                      }
                    </span>
                  </div>
                  {current_value !== undefined && (
                    <div className="text-gray-700 dark:text-gray-300 font-mono">
                      Current: {typeof current_value === 'number' ? current_value.toFixed(2) : current_value}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Show loading state for options details */}
      {loadingStrikes && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
          <div className="text-sm text-gray-600 dark:text-gray-400">Generating optimal strike prices...</div>
        </div>
      )}

      {/* If we have options details, show them */}
      {optionsDetails && !loadingStrikes && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
            Options Strategy Details
          </h4>
          <div className="bg-gray-50 dark:bg-gray-900 rounded p-4">
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-3">
              {optionsDetails.description}
            </div>
            <div className="grid grid-cols-1 gap-2 mb-3">
              {optionsDetails.legs
                .sort((a, b) => (a.order || 0) - (b.order || 0)) // Sort by execution order
                .map((leg, index) => (
                <div key={index} className="flex items-center justify-between text-sm border-l-2 pl-3 py-2" style={{
                  borderLeftColor: leg.order === 1 ? '#ef4444' : leg.order === 2 ? '#f97316' : leg.order === 3 ? '#eab308' : '#22c55e'
                }}>
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        leg.action === 'BUY' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                        leg.action === 'SELL' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
                        'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                      }`}>
                        {leg.action}
                      </span>
                      <span className="font-medium">
                        {leg.type} {leg.strike.toLocaleString('en-IN')}
                      </span>
                      {leg.premium && (
                        <span className="text-xs text-gray-500">
                          @₹{leg.premium}
                        </span>
                      )}
                      <span className="text-xs bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded">
                        #{leg.order || index + 1}
                      </span>
                    </div>
                    {leg.purpose && (
                      <div className="text-xs text-gray-600 dark:text-gray-400">
                        {leg.purpose}
                      </div>
                    )}
                  </div>
                  <span className="text-gray-500 text-xs">×{leg.quantity}</span>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-3 gap-4 text-xs mb-3">
              <div>
                <div className="text-gray-500">Max Profit</div>
                <div className="font-semibold text-green-600">{optionsDetails.maxProfit}</div>
              </div>
              <div>
                <div className="text-gray-500">Max Loss</div>
                <div className="font-semibold text-red-600">{optionsDetails.maxLoss}</div>
              </div>
              <div>
                <div className="text-gray-500">Breakeven</div>
                <div className="font-semibold text-gray-900 dark:text-white">{optionsDetails.breakeven}</div>
              </div>
            </div>

            {optionsDetails.rationale && (
              <div className="text-xs text-gray-600 dark:text-gray-400 bg-blue-50 dark:bg-blue-900/20 p-3 rounded">
                <div className="font-medium text-blue-800 dark:text-blue-200 mb-2">Strategy Analysis:</div>
                <div className="whitespace-pre-line">{optionsDetails.rationale}</div>

                {optionsDetails.marketAnalysis && (
                  <div className="mt-2 pt-2 border-t border-blue-200 dark:border-blue-700">
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>Volatility: {optionsDetails.marketAnalysis.volatility}%</div>
                      <div>RSI: {optionsDetails.marketAnalysis.rsi}</div>
                      <div>Trend: {optionsDetails.marketAnalysis.trend}</div>
                      <div>Confidence: {(optionsDetails.marketAnalysis.confidence * 100).toFixed(0)}%</div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Instrument & Timestamp */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
        <div className="flex justify-between text-sm">
          <span className="text-gray-600 dark:text-gray-400">
            {displayInstrument}
          </span>
          <span className="text-gray-500 dark:text-gray-400">
            {formatTimestampForDisplay(latestDecision?.timestamp || activeSignal?.timestamp)}
          </span>
        </div>
      </div>
    </div>
  )
}, (prevProps, nextProps) => {
  // Custom comparison function - component never receives props, so always return true
  return true
})